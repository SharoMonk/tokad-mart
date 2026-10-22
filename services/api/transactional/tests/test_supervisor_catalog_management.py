"""Supervisor catalog mutations preserve role, scope, and ledger rules."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    AuditEvent, InventoryItem, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal,
    Product, ProductBarcode, Sale,
)


@pytest.fixture
def catalog_users(db):
    location = POSLocation.objects.create(code="CAT", name="Catalog shop")
    terminal = POSTerminal.objects.create(location=location, code="CAT-01", name="Register")
    users = []
    for name, role in (
        ("catalog-manager", POSOperator.Role.SUPERVISOR),
        ("catalog-cashier", POSOperator.Role.OPERATOR),
    ):
        user = get_user_model().objects.create_user(name, password="test", is_staff=True)
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        users.append(user)
    return users


def post(client, path, body):
    return client.post(path, json.dumps(body), content_type="application/json")


def product_payload(**overrides):
    return {
        "location_code": "CAT", "terminal_code": "CAT-01",
        "sku": "RICE-NEW", "name": "Rice New", "currency": "NGN",
        "unit_price_minor": 250000, **overrides,
    }


@pytest.mark.django_db
def test_supervisor_registers_product_without_inventing_stock(catalog_users):
    manager, cashier = catalog_users
    url = "/api/transactional/pos/manage/products/"
    client = Client()
    client.force_login(cashier)
    assert post(client, url, product_payload()).status_code == 403
    client.force_login(manager)
    assert post(client, url, product_payload(location_code="OTHER")).status_code == 403
    created = post(client, url, product_payload())
    assert created.status_code == 201
    product = Product.objects.get(sku="RICE-NEW")
    assert created.json()["product"]["id"] == product.pk
    assert product.unit_price_minor == 250000
    assert InventoryItem.objects.filter(product=product).count() == 0
    assert Sale.objects.count() == 0
    assert post(client, url, product_payload()).status_code == 409
    assert Product.objects.filter(sku="RICE-NEW").count() == 1
    assert AuditEvent.objects.filter(action="product.created").count() == 1


@pytest.mark.django_db
def test_barcode_mapping_is_idempotent_and_rejects_collision(catalog_users):
    manager, cashier = catalog_users
    product = Product.objects.create(sku="RICE-NEW", name="Rice", unit_price_minor=250000)
    other = Product.objects.create(sku="OTHER", name="Other", unit_price_minor=150000)
    url = f"/api/transactional/pos/manage/products/{product.pk}/barcodes/"
    payload = {"location_code": "CAT", "terminal_code": "CAT-01", "code": "0012345678905"}
    client = Client()
    client.force_login(cashier)
    assert post(client, url, payload).status_code == 403
    client.force_login(manager)
    assert post(client, url, payload).status_code == 201
    assert post(client, url, payload).status_code == 200
    assert ProductBarcode.objects.count() == 1
    assert ProductBarcode.objects.get().code == "0012345678905"
    assert AuditEvent.objects.filter(action="product.barcode_added").count() == 1
    assert post(client, url, {**payload, "code": "OTHER"}).status_code == 409
    assert post(client, f"/api/transactional/pos/manage/products/{other.pk}/barcodes/", payload).status_code == 409
    response = client.get(url, {"location_code": "CAT", "terminal_code": "CAT-01"})
    assert response.status_code == 200
    assert response.json()["product"]["barcodes"] == ["0012345678905"]


@pytest.mark.django_db
def test_product_creation_rejects_invalid_price_and_barcode_sku_conflicts(catalog_users):
    manager, _ = catalog_users
    client = Client()
    client.force_login(manager)
    url = "/api/transactional/pos/manage/products/"
    assert post(client, url, product_payload(unit_price_minor=True)).status_code == 400
    assert post(client, url, product_payload(unit_price_minor=0)).status_code == 400
    assert post(client, url, product_payload(currency="USD")).status_code == 400
    original = Product.objects.create(sku="ORIGINAL", name="Original", unit_price_minor=10000)
    ProductBarcode.objects.create(product=original, code="RESERVED")
    assert post(client, url, product_payload(sku="RESERVED")).status_code == 409
    assert Product.objects.filter(sku="RESERVED").count() == 0
