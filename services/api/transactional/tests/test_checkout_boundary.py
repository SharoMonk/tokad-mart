from unittest.mock import Mock, patch

import pytest

from transactional.models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
    Payment,
    PaymentRefund,
    Product,
    Sale,
    SaleLine,
)
from transactional.payment_initiation import request_external_payment_initialization
from transactional.payment_services import process_pos_cash_sale
from transactional.services import CheckoutLine


def make_product(*, quantity=5):
    product = Product.objects.create(
        sku="SKU-CHECKOUT-BOUNDARY-001",
        name="Checkout Boundary Product",
        currency="NGN",
        unit_price_minor=1000,
    )
    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=quantity,
    )
    return product


@pytest.mark.django_db
def test_pos_cash_checkout_rolls_back_every_mutation_when_final_audit_fails():
    product = make_product()

    with patch(
        "transactional.payment_services.AuditEvent.objects.create",
        side_effect=RuntimeError("simulated final audit failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated final audit failure"):
            process_pos_cash_sale(
                lines=[CheckoutLine(product_id=product.id, quantity=2)],
                location_code="MAIN",
                currency="NGN",
                amount_minor=2000,
                sale_idempotency_key="checkout-boundary-sale-001",
                payment_idempotency_key="checkout-boundary-payment-001",
                provider_reference="CHECKOUT-BOUNDARY-001",
            )

    assert Sale.objects.count() == 0
    assert SaleLine.objects.count() == 0
    assert Payment.objects.count() == 0
    assert PaymentRefund.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert AuditEvent.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 5


@pytest.mark.django_db
def test_external_payment_request_rolls_back_payment_when_outbox_enqueue_fails():
    product = make_product()

    sale = Sale.objects.create(
        location_code="MAIN",
        currency="NGN",
        subtotal_minor=1000,
        total_minor=1000,
        status=Sale.Status.PENDING_PAYMENT,
    )
    SaleLine.objects.create(
        sale=sale,
        product=product,
        sku_snapshot=product.sku,
        name_snapshot=product.name,
        quantity=1,
        unit_price_minor=product.unit_price_minor,
        line_total_minor=1000,
    )

    provider = Mock(name="PaymentProvider")
    provider.name = "PAYSTACK"

    with patch(
        "transactional.payment_initiation.enqueue_outbox_event",
        side_effect=RuntimeError("simulated outbox enqueue failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated outbox enqueue failure"):
            request_external_payment_initialization(
                sale_id=sale.id,
                customer_email="customer@example.com",
                provider=provider,
                idempotency_key="checkout-boundary-payment-002",
            )

    assert Payment.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert AuditEvent.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 5
