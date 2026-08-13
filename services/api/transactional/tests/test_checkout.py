import pytest
from django.db import IntegrityError

from transactional.models import InventoryItem, Product
from transactional.services import CheckoutError, CheckoutLine, checkout_sale


@pytest.mark.django_db
def test_checkout_creates_sale_and_decrements_inventory():
    product = Product.objects.create(sku="SKU-001", name="Test Product", currency="NGN", unit_price_minor=1500)
    item = InventoryItem.objects.create(product=product, location_code="MAIN", quantity=5)

    result = checkout_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="checkout-001",
    )

    assert result.total_minor == 3000
    item.refresh_from_db()
    assert item.quantity == 3


@pytest.mark.django_db
def test_checkout_retry_returns_same_result():
    product = Product.objects.create(sku="SKU-002", name="Retry Product", currency="NGN", unit_price_minor=1000)
    InventoryItem.objects.create(product=product, location_code="MAIN", quantity=5)
    kwargs = dict(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="checkout-retry-001",
    )

    first = checkout_sale(**kwargs)
    second = checkout_sale(**kwargs)

    assert first == second
    assert InventoryItem.objects.get(product=product).quantity == 4
