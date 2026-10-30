"""Exact physical barcode lookup is secure, unambiguous and stock scoped."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product, ProductBarcode,
)


@pytest.fixture
def barcode_operator(db):
    user = get_user_model().objects.create_user(
        "barcode-cashier", password="test", is_staff=True
    )
    location = POSLocation.objects.create(code="MAIN", name="Main")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="T1")
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    product = Product.objects.create(
        sku="INTERNAL-RICE", name="Rice", currency="NGN",
        unit_price_minor=350000,
    )
    InventoryItem.objects.create(product=product, location_code="MAIN", quantity=7)
    ProductBarcode.objects.create(product=product, code="0012345678905")
    client = Client()
    client.force_login(user)
    return client, product


def lookup(client, code, location="MAIN", terminal="T1"):
    return client.get("/api/transactional/pos/barcode/", {
        "location_code": location, "terminal_code": terminal, "code": code
    })


@pytest.mark.django_db
def test_physical_barcode_and_internal_sku_resolve_same_product(barcode_operator):
    client, product = barcode_operator
    for code in ("0012345678905", "INTERNAL-RICE"):
        response = lookup(client, code)
        assert response.status_code == 200
        item = response.json()["product"]
        assert item["id"] == product.id
        assert item["stock"] == 7
        assert item["unit_price_minor"] == 350000
        assert item["sku"] == "INTERNAL-RICE"
    assert lookup(client, "012345678905").status_code == 404  # leading zero required
    assert lookup(client, "001234567890").status_code == 404  # never partial match


@pytest.mark.django_db
def test_barcode_scope_and_access_restrictions(barcode_operator):
    client, _ = barcode_operator
    assert lookup(client, "0012345678905", location="OTHER").status_code == 403
    assert lookup(client, "0012345678905", terminal="OTHER").status_code == 403
    assert lookup(Client(), "0012345678905").status_code in (401, 403)
    assert lookup(client, " 0012345678905").status_code == 400


@pytest.mark.django_db
def test_conflicting_barcode_and_sku_rejected(barcode_operator):
    client, _ = barcode_operator
    Product.objects.create(
        sku="0012345678905", name="Different item",
        currency="NGN", unit_price_minor=15000,
    )
    response = lookup(client, "0012345678905")
    assert response.status_code == 409
    assert response.json()["error"] == "barcode_sku_conflict"
