import threading

import pytest
from django.db import close_old_connections
from django.test import TransactionTestCase

from transactional.exceptions import PaymentAmountMismatchError
from transactional.models import (
    InventoryItem,
    InventoryMovement,
    OutboxEvent,
    Payment,
    PaymentRefund,
    PaymentWebhookEvent,
    Product,
    Sale,
)
from transactional.payment_providers import VerifiedPayment
from transactional.payment_refunds import request_refund
from transactional.payment_services import create_pending_sale, record_successful_payment
from transactional.payment_webhooks import process_payment_webhook
from transactional.services import CheckoutLine


class PaymentConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def _make_pending_payment(self):
        product = Product.objects.create(
            sku="SKU-PAY-CONCURRENT-001",
            name="Concurrent Payment Product",
            currency="NGN",
            unit_price_minor=2500,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=1,
        )
        sale = create_pending_sale(
            lines=[CheckoutLine(product_id=product.id, quantity=1)],
            location_code="MAIN",
            currency="NGN",
            idempotency_key="payment-concurrency-sale-001",
        )
        payment = Payment.objects.create(
            sale_id=sale.sale_id,
            provider="TEST",
            provider_reference="TEST-PAY-CONCURRENT-001",
            idempotency_key="payment-concurrency-payment-001",
            method=Payment.Method.EXTERNAL,
            amount_minor=2500,
            currency="NGN",
            status=Payment.Status.PENDING,
        )
        return product, sale, payment

    def _make_paid_payment(self):
        product = Product.objects.create(
            sku="SKU-REFUND-CONCURRENT-001",
            name="Concurrent Refund Product",
            currency="NGN",
            unit_price_minor=2500,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=5,
        )
        sale = create_pending_sale(
            lines=[CheckoutLine(product_id=product.id, quantity=1)],
            location_code="MAIN",
            currency="NGN",
            idempotency_key="refund-concurrency-sale-001",
        )
        payment = record_successful_payment(
            sale_id=sale.sale_id,
            amount_minor=2500,
            currency="NGN",
            method=Payment.Method.EXTERNAL,
            provider="TEST",
            provider_reference="TEST-REFUND-CONCURRENT-001",
            idempotency_key="refund-concurrency-payment-001",
        )
        return Payment.objects.get(id=payment.payment_id)

    def test_concurrent_duplicate_webhook_completes_payment_and_sale_once(self):
        product, sale, payment = self._make_pending_payment()
        verified = VerifiedPayment(
            provider="TEST",
            provider_reference=payment.provider_reference,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            succeeded=True,
        )

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(
                    process_payment_webhook(
                        provider="TEST",
                        event_id="evt-concurrent-payment-001",
                        provider_reference=payment.provider_reference,
                        verified=verified,
                    )
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)
        assert not errors
        assert len(results) == 2
        assert sorted(result.already_processed for result in results) == [False, True]

        payment.refresh_from_db()
        sale = Sale.objects.get(pk=sale.sale_id)

        assert payment.status == Payment.Status.SUCCEEDED
        assert sale.status == Sale.Status.COMPLETED
        assert InventoryItem.objects.get(product=product).quantity == 0
        assert InventoryMovement.objects.count() == 1
        assert PaymentWebhookEvent.objects.count() == 1

    def test_concurrent_refund_requests_with_same_key_create_one_refund(self):
        payment = self._make_paid_payment()
        provider = type("Provider", (), {"name": "TEST"})()

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(
                    request_refund(
                        payment_id=payment.id,
                        amount_minor=1000,
                        provider=provider,
                        idempotency_key="refund-concurrency-same-key-001",
                    )
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)
        assert not errors
        assert len(results) == 2
        assert results[0] == results[1]
        assert PaymentRefund.objects.count() == 1
        assert OutboxEvent.objects.count() == 1

    def test_concurrent_partial_refunds_cannot_exceed_payment_total(self):
        payment = self._make_paid_payment()
        provider = type("Provider", (), {"name": "TEST"})()

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker(suffix):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(
                    request_refund(
                        payment_id=payment.id,
                        amount_minor=1500,
                        provider=provider,
                        idempotency_key=f"refund-concurrency-partial-{suffix}",
                    )
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=("a",)),
            threading.Thread(target=worker, args=("b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 1
        assert len(errors) == 1
        assert isinstance(errors[0], PaymentAmountMismatchError)

        assert PaymentRefund.objects.count() == 1
        assert OutboxEvent.objects.count() == 1
        refund = PaymentRefund.objects.get()
        assert refund.amount_minor == 1500
        assert Payment.objects.get(pk=payment.id).status == Payment.Status.SUCCEEDED
