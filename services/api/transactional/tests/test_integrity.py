import pytest

from transactional.models import AuditEvent, InventoryItem, InventoryMovement, Product, Sale, SaleLine
from transactional.services import CheckoutError, CheckoutLine, checkout_sale


@pytest.mark.django_db
def test_insufficient_stock_rolls_back_entire_checkout():
    product = Product.objects.create(
        sku="SKU-STOCK-001", name="Limited Product", currency="NGN", unit_price_minor=2500
    )
    item = InventoryItem.objects.create(product=product, location_code="MAIN", quantity=1)

    with pytest.raises(CheckoutError, match="insufficient stock"):
        checkout_sale(
            lines=[CheckoutLine(product_id=product.id, quantity=2)],
            location_code="MAIN",
            currency="NGN",
            idempotency_key="stock-failure-001",
        )

    item.refresh_from_db()
    assert item.quantity == 1
    assert Sale.objects.count() == 0
    assert SaleLine.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_idempotency_key_reuse_with_different_request_is_rejected():
    product = Product.objects.create(
        sku="SKU-IDEMP-001", name="Idempotent Product", currency="NGN", unit_price_minor=1000
    )
    InventoryItem.objects.create(product=product, location_code="MAIN", quantity=5)

    checkout_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="same-key-001",
    )

    with pytest.raises(CheckoutError, match="different request"):
        checkout_sale(
            lines=[CheckoutLine(product_id=product.id, quantity=2)],
            location_code="MAIN",
            currency="NGN",
            idempotency_key="same-key-001",
        )

    assert InventoryItem.objects.get(product=product, location_code="MAIN").quantity == 4
    assert Sale.objects.count() == 1
