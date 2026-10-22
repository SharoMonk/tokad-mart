import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    CashierShift, InventoryItem, InventoryMovement, Payment, POSLocation,
    POSOperator, POSOperatorLocation, POSOperatorTerminal, POSTerminal, Product, Sale,
)


@pytest.mark.django_db
def test_open_cash_shift_sale_retry_and_close_reconcile_once():
    user = get_user_model().objects.create_user(
        username="shift-cashier", password="secret", is_staff=True
    )
    location = POSLocation.objects.create(code="MAIN", name="Main")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="Till")
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    product = Product.objects.create(
        sku="SHIFT-RICE", name="Rice", currency="NGN", unit_price_minor=350000
    )
    stock = InventoryItem.objects.create(product=product, location_code="MAIN", quantity=20)
    client = Client()
    client.force_login(user)

    path = "/api/transactional/pos/shifts/"
    scope = {"location_code": "MAIN", "terminal_code": "T1"}
    opening = client.post(path, json.dumps({**scope, "opening_cash_minor": 100000}),
                          content_type="application/json")
    assert opening.status_code == 201
    shift_id = opening.json()["shift"]["id"]
    assert client.get(path, scope).json()["shift"]["id"] == shift_id
    duplicate = client.post(path, json.dumps({**scope, "opening_cash_minor": 0}),
                            content_type="application/json")
    assert duplicate.status_code == 400

    body = {
        **scope, "shift_id": shift_id, "currency": "NGN",
        "lines": [{"product_id": product.pk, "quantity": 2}],
        "amount_minor": 700000,
        "sale_idempotency_key": "shift-sale-key",
        "payment_idempotency_key": "shift-payment-key",
        "provider_reference": "SHIFT-CASH-REFERENCE",
    }
    sale_url = "/api/transactional/pos/sales/"
    first = client.post(sale_url, json.dumps(body), content_type="application/json")
    second = client.post(sale_url, json.dumps(body), content_type="application/json")
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert Sale.objects.get().shift_id == shift_id
    assert Payment.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    stock.refresh_from_db()
    assert stock.quantity == 18

    closing = client.post(
        f"/api/transactional/pos/shifts/{shift_id}/close/",
        json.dumps({"closing_cash_minor": 800000}),
        content_type="application/json",
    )
    assert closing.status_code == 200
    details = closing.json()["shift"]
    assert details["expected_cash_minor"] == 800000
    assert details["variance_minor"] == 0
    assert CashierShift.objects.get(pk=shift_id).status == CashierShift.Status.CLOSED
    assert client.get(path, scope).json()["shift"] is None

    after_close = client.post(sale_url, json.dumps({
        **body, "sale_idempotency_key": "shift-new-sale",
        "payment_idempotency_key": "shift-new-payment",
        "provider_reference": "SHIFT-CASH-NEW",
    }), content_type="application/json")
    assert after_close.status_code == 409
    assert Sale.objects.count() == 1
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_shift_endpoints_require_authentication():
    client = Client()
    assert client.get("/api/transactional/pos/shifts/").status_code in (401, 403)
    assert client.post(
        "/api/transactional/pos/shifts/", "{}", content_type="application/json"
    ).status_code in (401, 403)
