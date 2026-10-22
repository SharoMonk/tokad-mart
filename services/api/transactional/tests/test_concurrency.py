import threading
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TransactionTestCase

from transactional.services import CheckoutError, CheckoutLine, checkout_sale
from transactional.payment_services import process_pos_cash_sale

from transactional.models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
    Payment,
    Product,
    Sale,
    SaleLine,
)


class CheckoutConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_only_one_checkout_can_sell_last_unit(self):
        product = Product.objects.create(
            sku="SKU-CONCURRENT-001",
            name="Concurrent Product",
            currency="NGN",
            unit_price_minor=1000,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=1,
        )

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def attempt(idempotency_key):
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                result = checkout_sale(
                    lines=[
                        CheckoutLine(
                            product_id=product.id,
                            quantity=1,
                        )
                    ],
                    location_code="MAIN",
                    currency="NGN",
                    idempotency_key=idempotency_key,
                )
                results.append(result)

            except CheckoutError as exc:
                errors.append(exc)

            finally:
                close_old_connections()

        threads = [
            threading.Thread(
                target=attempt,
                args=("concurrent-a",),
            ),
            threading.Thread(
                target=attempt,
                args=("concurrent-b",),
            ),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)

        assert len(results) == 1
        assert len(errors) == 1
        assert "insufficient stock" in str(errors[0])

        item = InventoryItem.objects.get(
            product=product,
            location_code="MAIN",
        )

        assert item.quantity == 0
        assert Sale.objects.count() == 1
        assert SaleLine.objects.count() == 1
        assert InventoryMovement.objects.count() == 1
        assert AuditEvent.objects.count() == 1
        assert IdempotencyRecord.objects.count() == 1

    def test_concurrent_retry_with_same_idempotency_key_returns_same_result(self):
        product = Product.objects.create(
            sku="SKU-CONCURRENT-IDEMP-001",
            name="Concurrent Idempotent Product",
            currency="NGN",
            unit_price_minor=1000,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=2,
        )

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def attempt():
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                result = checkout_sale(
                    lines=[
                        CheckoutLine(
                            product_id=product.id,
                            quantity=1,
                        )
                    ],
                    location_code="MAIN",
                    currency="NGN",
                    idempotency_key="concurrent-same-key-001",
                )
                results.append(result)

            except Exception as exc:
                errors.append(exc)

            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=attempt),
            threading.Thread(target=attempt),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)

        assert not errors
        assert len(results) == 2
        assert results[0] == results[1]

        item = InventoryItem.objects.get(
            product=product,
            location_code="MAIN",
        )

        assert item.quantity == 1
        assert Sale.objects.count() == 1
        assert SaleLine.objects.count() == 1
        assert InventoryMovement.objects.count() == 1
        assert AuditEvent.objects.count() == 1
        assert IdempotencyRecord.objects.count() == 1

    def test_concurrent_full_cash_checkout_with_same_keys_returns_same_result(self):
        product = Product.objects.create(
            sku="SKU-CONCURRENT-CASH-001",
            name="Concurrent Cash Product",
            currency="NGN",
            unit_price_minor=1000,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=2,
        )

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(
                    process_pos_cash_sale(
                        lines=[CheckoutLine(product_id=product.id, quantity=1)],
                        location_code="MAIN",
                        currency="NGN",
                        amount_minor=1000,
                        sale_idempotency_key="concurrent-cash-sale-001",
                        payment_idempotency_key="concurrent-cash-payment-001",
                        provider_reference="CONCURRENT-CASH-001",
                    )
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)
        assert not errors
        assert len(results) == 2
        assert results[0] == results[1]

        item = InventoryItem.objects.get(product=product, location_code="MAIN")
        assert item.quantity == 1
        assert Sale.objects.count() == 1
        assert SaleLine.objects.count() == 1
        assert Payment.objects.count() == 1
        assert InventoryMovement.objects.count() == 1
        assert AuditEvent.objects.count() == 2
        assert IdempotencyRecord.objects.count() == 1

    def test_concurrent_full_cash_checkouts_cannot_oversell_last_unit(self):
        product = Product.objects.create(
            sku="SKU-CONCURRENT-CASH-LAST-001",
            name="Concurrent Cash Last Unit",
            currency="NGN",
            unit_price_minor=1000,
        )
        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=1,
        )

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def attempt(suffix):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(
                    process_pos_cash_sale(
                        lines=[CheckoutLine(product_id=product.id, quantity=1)],
                        location_code="MAIN",
                        currency="NGN",
                        amount_minor=1000,
                        sale_idempotency_key=f"concurrent-cash-last-sale-{suffix}",
                        payment_idempotency_key=f"concurrent-cash-last-payment-{suffix}",
                        provider_reference=f"CONCURRENT-CASH-LAST-{suffix}",
                    )
                )
            except CheckoutError as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=attempt, args=("a",)),
            threading.Thread(target=attempt, args=("b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 1
        assert len(errors) == 1
        assert "insufficient stock" in str(errors[0])

        item = InventoryItem.objects.get(product=product, location_code="MAIN")
        assert item.quantity == 0
        assert Sale.objects.count() == 1
        assert SaleLine.objects.count() == 1
        assert Payment.objects.count() == 1
        assert InventoryMovement.objects.count() == 1
        assert AuditEvent.objects.count() == 2
        assert IdempotencyRecord.objects.count() == 1

    def test_reusing_idempotency_key_with_different_request_fails(self):
        product = Product.objects.create(
            sku="SKU-IDEMP-MISMATCH-001",
            name="Idempotency Product",
            currency="NGN",
            unit_price_minor=1000,
        )

        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=5,
        )

        checkout_sale(
            lines=[
                CheckoutLine(
                    product_id=product.id,
                    quantity=1,
                )
            ],
            location_code="MAIN",
            currency="NGN",
            idempotency_key="same-key",
        )

        with self.assertRaises(CheckoutError) as context:
            checkout_sale(
                lines=[
                    CheckoutLine(
                        product_id=product.id,
                        quantity=2,
                    )
                ],
                location_code="MAIN",
                currency="NGN",
                idempotency_key="same-key",
            )

        assert "different request" in str(context.exception)
        assert Sale.objects.count() == 1
        assert InventoryItem.objects.get(
                product=product,
                location_code="MAIN",
            ).quantity == 4

    def test_checkout_rolls_back_when_sale_line_creation_fails(self):
        product = Product.objects.create(
            sku="SKU-ROLLBACK-SALELINE-001",
            name="Rollback SaleLine Product",
            currency="NGN",
            unit_price_minor=1000,
        )

        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=5,
        )

        with patch(
            "transactional.services.SaleLine.objects.create",
            side_effect=RuntimeError("simulated SaleLine failure"),
        ):
            with self.assertRaises(RuntimeError) as context:
                checkout_sale(
                    lines=[
                        CheckoutLine(
                            product_id=product.id,
                            quantity=1,
                        )
                    ],
                    location_code="MAIN",
                    currency="NGN",
                    idempotency_key="rollback-saleline-001",
                )

        assert "simulated SaleLine failure" in str(context.exception)

        # The entire checkout transaction must have rolled back.
        assert Sale.objects.count() == 0
        assert SaleLine.objects.count() == 0
        assert InventoryMovement.objects.count() == 0
        assert AuditEvent.objects.count() == 0
        assert IdempotencyRecord.objects.count() == 0

        # Inventory must be restored to its original quantity.
        assert (
            InventoryItem.objects.get(
                product=product,
                location_code="MAIN",
            ).quantity
            == 5
        )

    def test_checkout_rolls_back_when_inventory_movement_creation_fails(self):
        product = Product.objects.create(
            sku="SKU-ROLLBACK-MOVEMENT-001",
            name="Rollback Movement Product",
            currency="NGN",
            unit_price_minor=1000,
        )

        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=5,
        )

        with patch(
            "transactional.services.InventoryMovement.objects.create",
            side_effect=RuntimeError("simulated inventory movement failure"),
        ):
            with self.assertRaises(RuntimeError) as context:
                checkout_sale(
                    lines=[
                        CheckoutLine(
                            product_id=product.id,
                            quantity=1,
                        )
                    ],
                    location_code="MAIN",
                    currency="NGN",
                    idempotency_key="rollback-movement-001",
                )

        assert "simulated inventory movement failure" in str(context.exception)

        # Sale and all related transactional state must be rolled back.
        assert Sale.objects.count() == 0
        assert SaleLine.objects.count() == 0
        assert InventoryMovement.objects.count() == 0
        assert AuditEvent.objects.count() == 0
        assert IdempotencyRecord.objects.count() == 0

        # Inventory must not remain decremented.
        assert (
            InventoryItem.objects.get(
                product=product,
                location_code="MAIN",
            ).quantity
            == 5
        )

    def test_same_idempotency_key_can_retry_after_rollback(self):
        product = Product.objects.create(
            sku="SKU-ROLLBACK-RETRY-001",
            name="Rollback Retry Product",
            currency="NGN",
            unit_price_minor=1000,
        )

        InventoryItem.objects.create(
            product=product,
            location_code="MAIN",
            quantity=5,
        )

        idempotency_key = "rollback-retry-001"

        # First attempt deliberately fails.
        with patch(
            "transactional.services.InventoryMovement.objects.create",
            side_effect=RuntimeError("simulated failure"),
        ):
            with self.assertRaises(RuntimeError):
                checkout_sale(
                    lines=[
                        CheckoutLine(
                            product_id=product.id,
                            quantity=1,
                        )
                    ],
                    location_code="MAIN",
                    currency="NGN",
                    idempotency_key=idempotency_key,
                )

        # The failed transaction must not consume the idempotency key.
        assert IdempotencyRecord.objects.count() == 0
        assert Sale.objects.count() == 0

        item = InventoryItem.objects.get(
            product=product,
            location_code="MAIN",
        )
        assert item.quantity == 5

        # Retry with the exact same request/key.
        result = checkout_sale(
            lines=[
                CheckoutLine(
                    product_id=product.id,
                    quantity=1,
                )
            ],
            location_code="MAIN",
            currency="NGN",
            idempotency_key=idempotency_key,
        )

        # The retry should now succeed normally.
        assert result.total_minor == 1000

        assert Sale.objects.count() == 1
        assert SaleLine.objects.count() == 1
        assert InventoryMovement.objects.count() == 1
        assert AuditEvent.objects.count() == 1
        assert IdempotencyRecord.objects.count() == 1

        assert (
            InventoryItem.objects.get(
                product=product,
                location_code="MAIN",
            ).quantity
            == 4
        )
