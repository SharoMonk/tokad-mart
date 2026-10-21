"""Cookie-session cashier login and shift-authorized cash-sale security tests."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from transactional.models import (
    CashierShift, InventoryItem, InventoryMovement, Payment, POSLocation,
    POSOperator, POSOperatorLocation, POSOperatorTerminal, POSTerminal, Product, Sale,
)


@pytest.fixture
def setup_cashier(db):
    user = get_user_model().objects.create_user(
        username="shift-cashier", password="test-password", is_staff=True,
    )
    store = POSLocation.objects.create(code="MAIN", name="Main")
    terminal = POSTerminal.objects.create(location=store, code="MAIN-01", name="Main terminal")
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=store)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    product = Product.objects.create(
        sku="SHIFT-DEMO", name="Demo soap", currency="NGN", unit_price_minor=85000,
    )
    item = InventoryItem.objects.create(product=product, location_code="MAIN", quantity=10)
    return user, product, item


def post(client, path, body, csrf=None):
    headers = {"HTTP_X_CSRFTOKEN": csrf} if csrf else {}
    return client.post(path, data=json.dumps(body), content_type="application/json", **headers)


@pytest.mark.django_db
def test_session_login_requires_csrf_and_logout_invalidates_session(setup_cashier):
    client = Client(enforce_csrf_checks=True)
    assert post(client, "/api/transactional/pos/login/", {
        "username": "shift-cashier", "password": "test-password"
    }).status_code == 403
    assert client.get("/api/transactional/pos/session/").status_code == 200
    csrf = client.cookies["csrftoken"].value
    logged_in = post(client, "/api/transactional/pos/login/", {
        "username": "shift-cashier", "password": "test-password"
    }, csrf)
    assert logged_in.status_code == 200
    assert client.get("/api/transactional/pos/session/").json()["authenticated"]
    assert client.get("/api/transactional/pos/scope/").status_code == 200
    assert post(client, "/api/transactional/pos/logout/", {}, client.cookies["csrftoken"].value).status_code == 200
    assert not client.get("/api/transactional/pos/session/").json()["authenticated"]


@pytest.mark.django_db
def test_shift_required_and_retry_deducts_stock_once(setup_cashier):
    user, product, item = setup_cashier
    client = Client()
    client.force_login(user)
    body = {
        "location_code": "MAIN", "terminal_code": "MAIN-01",
        "shift_id": 99999,
        "lines": [{"product_id": product.pk, "quantity": 2}],
        "currency": "NGN", "amount_minor": 170000,
        "sale_idempotency_key": "shift-sale-1",
        "payment_idempotency_key": "shift-payment-1",
        "provider_reference": "SHIFT-CASH-1",
    }
    path = "/api/transactional/pos/shift-sales/"
    assert post(client, path, body).status_code == 404
    opened = post(client, "/api/transactional/pos/shifts/", {
        "location_code": "MAIN", "terminal_code": "MAIN-01",
        "opening_cash_minor": 100000,
    })
    assert opened.status_code == 201
    shift_id = opened.json()["shift"]["id"]
    body["shift_id"] = shift_id
    first = post(client, path, body)
    retry = post(client, path, body)
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert Sale.objects.count() == Payment.objects.count() == InventoryMovement.objects.count() == 1
    assert Sale.objects.get().shift_id == shift_id
    item.refresh_from_db()
    assert item.quantity == 8

    closed = post(client, f"/api/transactional/pos/shifts/{shift_id}/close/", {
        "closing_cash_minor": 270000,
    })
    assert closed.status_code == 200
    assert closed.json()["shift"]["expected_cash_minor"] == 270000
    assert closed.json()["shift"]["variance_minor"] == 0
    assert post(client, path, body).status_code == 409
    assert Sale.objects.count() == 1
    assert InventoryMovement.objects.count() == 1


@pytest.mark.django_db
def test_shift_sale_requires_authenticated_session(setup_cashier):
    _, product, _ = setup_cashier
    body = {"shift_id": 1, "lines": [{"product_id": product.id, "quantity": 1}]}
    assert post(Client(), "/api/transactional/pos/shift-sales/", body).status_code in (401, 403)
