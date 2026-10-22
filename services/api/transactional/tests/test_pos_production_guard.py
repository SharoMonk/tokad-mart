"""Production checkout gate and session-only cashier endpoint regression tests."""
import base64
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from transactional.models import (
    InventoryItem, Payment, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product, Sale,
)


@pytest.fixture
def operator_setup(db):
    user = get_user_model().objects.create_user(
        username="secure-cashier", password="secret-password", is_staff=True
    )
    location = POSLocation.objects.create(code="STORE", name="Store")
    terminal = POSTerminal.objects.create(
        location=location, code="POS1", name="Register 1"
    )
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    product = Product.objects.create(
        sku="SECURE-ITEM", name="Secure item", unit_price_minor=1000, currency="NGN"
    )
    InventoryItem.objects.create(product=product, location_code="STORE", quantity=4)
    return user, product


@pytest.mark.django_db
def test_basic_credentials_cannot_access_session_only_pos_routes(operator_setup):
    secret = base64.b64encode(b"secure-cashier:secret-password").decode("ascii")
    client = Client(HTTP_AUTHORIZATION="Basic " + secret)
    assert client.get("/api/transactional/pos/scope/").status_code in (401, 403)
    assert client.get("/api/transactional/pos/catalog/", {
        "location_code": "STORE", "terminal_code": "POS1", "q": "Secure"
    }).status_code in (401, 403)
    assert client.get("/api/transactional/pos/shifts/", {
        "location_code": "STORE", "terminal_code": "POS1"
    }).status_code in (401, 403)


@pytest.mark.django_db
@override_settings(POS_ENABLE_LEGACY_CHECKOUT=False)
def test_legacy_checkout_disabled_without_creating_ledger_records(operator_setup):
    user, product = operator_setup
    client = Client()
    client.force_login(user)
    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps({
            "lines": [{"product_id": product.pk, "quantity": 1}],
            "location_code": "STORE", "terminal_code": "POS1",
            "currency": "NGN", "amount_minor": 1000,
            "sale_idempotency_key": "legacy-blocked",
            "payment_idempotency_key": "legacy-payment-blocked",
            "provider_reference": "legacy-reference-blocked"
        }),
        content_type="application/json",
    )
    assert response.status_code == 410
    assert response.json()["error"] == "legacy_checkout_disabled"
    assert Sale.objects.count() == Payment.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 4
