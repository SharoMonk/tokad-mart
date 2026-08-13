import threading

from django.db import close_old_connections
from django.test import TransactionTestCase

from transactional.services import CheckoutError, CheckoutLine, checkout_sale

from transactional.models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
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