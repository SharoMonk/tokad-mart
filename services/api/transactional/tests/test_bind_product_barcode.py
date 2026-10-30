"""Physical barcode management command protects product associations."""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from transactional.models import Product, ProductBarcode


@pytest.mark.django_db
def test_bind_product_barcode_is_idempotent_and_preserves_leading_zero():
    Product.objects.create(
        sku="RICE-1", name="Rice", currency="NGN", unit_price_minor=50000
    )
    for _ in range(2):
        call_command(
            "bind_product_barcode", sku="RICE-1",
            barcode="0012345678905", stdout=StringIO(),
        )
    assert ProductBarcode.objects.count() == 1
    assert ProductBarcode.objects.get().code == "0012345678905"


@pytest.mark.django_db
def test_bind_product_barcode_rejects_other_sku_collision():
    Product.objects.create(
        sku="RICE-1", name="Rice", currency="NGN", unit_price_minor=50000
    )
    Product.objects.create(
        sku="0012345678905", name="Other", currency="NGN",
        unit_price_minor=25000,
    )
    with pytest.raises(CommandError, match="conflicts"):
        call_command(
            "bind_product_barcode", sku="RICE-1", barcode="0012345678905"
        )
    assert ProductBarcode.objects.count() == 0
