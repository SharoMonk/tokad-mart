from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from transactional.exceptions import (
    PaymentAmountMismatchError,
    PaymentError,
    PaymentIdempotencyConflictError,
)
from transactional.models import InventoryItem, OutboxEvent, Payment, PaymentRefund, Product
from transactional.outbox_dispatcher import dispatch_outbox_events
from transactional.payment_outbox import REFUND_REQUESTED_EVENT, make_refund_outbox_handler
from transactional.payment_providers import PaymentProviderError, VerifiedPayment
from transactional.payment_refunds import reconcile_payment, request_refund
from transactional.payment_services import create_pending_sale, record_successful_payment
from transactional.services import CheckoutLine


def make_paid_payment():
    product = Product.objects.create(
        sku="SKU-REFUND-001",
        name="Refund Product",
        currency="NGN",
        unit_price_minor=2500,
    )
    InventoryItem.objects.create(product=product, location_code="MAIN", quantity=5)
    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="refund-sale-001",
    )
    payment = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=2500,
        currency="NGN",
        method=Payment.Method.EXTERNAL,
        provider="PAYSTACK",
        provider_reference="PSK-REFUND-001",
        idempotency_key="refund-payment-001",
    )
    return Payment.objects.get(id=payment.payment_id)


def dispatch_refund(provider):
    return dispatch_outbox_events({REFUND_REQUESTED_EVENT: make_refund_outbox_handler(provider)})


@pytest.mark.django_db
def test_request_refund_creates_request_and_outbox_event():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    result = request_refund(
        payment_id=payment.id,
        amount_minor=None,
        provider=provider,
        idempotency_key="refund-001",
    )

    payment.refresh_from_db()

    assert result.status == PaymentRefund.Status.REQUESTED
    assert result.amount_minor == 2500
    assert payment.status == Payment.Status.SUCCEEDED
    assert PaymentRefund.objects.count() == 1
    assert OutboxEvent.objects.count() == 1
    assert OutboxEvent.objects.get().event_type == REFUND_REQUESTED_EVENT
    provider.refund_payment.assert_not_called()


@pytest.mark.django_db
def test_dispatch_refund_completes_full_payment_refund():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    request_refund(
        payment_id=payment.id,
        amount_minor=None,
        provider=provider,
        idempotency_key="refund-dispatch-001",
    )

    result = dispatch_refund(provider)

    payment.refresh_from_db()
    refund = PaymentRefund.objects.get(idempotency_key="refund-dispatch-001")
    event = OutboxEvent.objects.get(idempotency_key="payment-refund:refund-dispatch-001")

    assert result.completed == 1
    assert refund.status == PaymentRefund.Status.SUCCEEDED
    assert payment.status == Payment.Status.REFUNDED
    assert event.status == OutboxEvent.Status.COMPLETED
    provider.refund_payment.assert_called_once_with(
        provider_reference="PSK-REFUND-001",
        amount_minor=2500,
    )


@pytest.mark.django_db
def test_request_refund_retry_is_idempotent():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    first = request_refund(
        payment_id=payment.id,
        amount_minor=1000,
        provider=provider,
        idempotency_key="refund-retry-001",
    )
    second = request_refund(
        payment_id=payment.id,
        amount_minor=1000,
        provider=provider,
        idempotency_key="refund-retry-001",
    )

    assert first == second
    assert first.status == PaymentRefund.Status.REQUESTED
    assert PaymentRefund.objects.count() == 1
    assert OutboxEvent.objects.count() == 1
    provider.refund_payment.assert_not_called()


@pytest.mark.django_db
def test_request_refund_rejects_amount_above_payment():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    with pytest.raises(PaymentAmountMismatchError):
        request_refund(
            payment_id=payment.id,
            amount_minor=2501,
            provider=provider,
            idempotency_key="refund-invalid-001",
        )

    assert PaymentRefund.objects.count() == 0
    assert OutboxEvent.objects.count() == 0
    provider.refund_payment.assert_not_called()


@pytest.mark.django_db
def test_request_refund_limits_cumulative_partial_refunds():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    first = request_refund(
        payment_id=payment.id,
        amount_minor=1500,
        provider=provider,
        idempotency_key="refund-partial-001",
    )

    dispatch_refund(provider)
    payment.refresh_from_db()

    assert first.status == PaymentRefund.Status.REQUESTED
    refund = PaymentRefund.objects.get(idempotency_key="refund-partial-001")
    assert refund.status == PaymentRefund.Status.SUCCEEDED
    assert payment.status == Payment.Status.SUCCEEDED

    with pytest.raises(PaymentAmountMismatchError):
        request_refund(
            payment_id=payment.id,
            amount_minor=1001,
            provider=provider,
            idempotency_key="refund-partial-overage-001",
        )


@pytest.mark.django_db
def test_request_refund_rejects_reuse_with_different_amount():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"

    request_refund(
        payment_id=payment.id,
        amount_minor=1000,
        provider=provider,
        idempotency_key="refund-conflict-001",
    )

    with pytest.raises(PaymentIdempotencyConflictError):
        request_refund(
            payment_id=payment.id,
            amount_minor=1500,
            provider=provider,
            idempotency_key="refund-conflict-001",
        )

    assert PaymentRefund.objects.count() == 1
    assert OutboxEvent.objects.count() == 1


@pytest.mark.django_db
def test_provider_failure_keeps_refund_requested_and_outbox_retryable():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"
    provider.refund_payment.side_effect = PaymentProviderError("provider unavailable")

    result = request_refund(
        payment_id=payment.id,
        amount_minor=1000,
        provider=provider,
        idempotency_key="refund-provider-failure-001",
    )

    dispatch_result = dispatch_refund(provider)
    payment.refresh_from_db()
    refund = PaymentRefund.objects.get(idempotency_key="refund-provider-failure-001")
    event = OutboxEvent.objects.get(idempotency_key="payment-refund:refund-provider-failure-001")

    assert result.status == PaymentRefund.Status.REQUESTED
    assert dispatch_result.failed == 1
    assert payment.status == Payment.Status.SUCCEEDED
    assert refund.status == PaymentRefund.Status.REQUESTED
    assert refund.provider_metadata["error"] == "provider unavailable"
    assert event.status == OutboxEvent.Status.FAILED


@pytest.mark.django_db
def test_provider_failure_can_be_retried_successfully():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"
    provider.refund_payment.side_effect = [
        PaymentProviderError("temporary failure"),
        None,
    ]

    request_refund(
        payment_id=payment.id,
        amount_minor=1000,
        provider=provider,
        idempotency_key="refund-retry-provider-001",
    )

    first_dispatch = dispatch_refund(provider)
    event = OutboxEvent.objects.get(idempotency_key="payment-refund:refund-retry-provider-001")
    event.available_at = timezone.now() - timedelta(seconds=1)
    event.save(update_fields=["available_at"])

    second_dispatch = dispatch_refund(provider)

    refund = PaymentRefund.objects.get(idempotency_key="refund-retry-provider-001")

    assert first_dispatch.failed == 1
    assert second_dispatch.completed == 1
    assert refund.status == PaymentRefund.Status.SUCCEEDED
    assert provider.refund_payment.call_count == 2


@pytest.mark.django_db
def test_reconcile_payment_matches_provider_state():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"
    provider.verify_payment.return_value = VerifiedPayment(
        provider="PAYSTACK",
        provider_reference=payment.provider_reference,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        succeeded=True,
    )

    result = reconcile_payment(payment_id=payment.id, provider=provider)

    assert result.matches is True
    assert result.local_status == Payment.Status.SUCCEEDED
    assert result.provider_status == "SUCCEEDED"


@pytest.mark.django_db
def test_reconcile_payment_detects_provider_amount_mismatch():
    payment = make_paid_payment()
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"
    provider.verify_payment.return_value = VerifiedPayment(
        provider="PAYSTACK",
        provider_reference=payment.provider_reference,
        amount_minor=payment.amount_minor - 100,
        currency=payment.currency,
        succeeded=True,
    )

    result = reconcile_payment(payment_id=payment.id, provider=provider)

    assert result.matches is False


@pytest.mark.django_db
def test_refund_requires_matching_provider():
    payment = make_paid_payment()
    provider = Mock(name="OtherProvider")
    provider.name = "OTHER"

    with pytest.raises(PaymentError, match="refund provider does not match"):
        request_refund(
            payment_id=payment.id,
            amount_minor=1000,
            provider=provider,
            idempotency_key="refund-provider-mismatch-001",
        )
