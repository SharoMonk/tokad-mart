"""End-to-end HTTP contract for canonical cash POS.

Exercises real Django routes and the single transactional inventory ledger.
Does not call or create any legacy commerce sale records.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    InventoryItem, InventoryMovement, Payment, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal, Product, Sale, SaleLine,
)


@pytest.mark.django_db
def test_cash_sale_catalog_receipt_and_retry_share_one_ledger():
    user = get_user_model().objects.create_user(
        username="e2e-cashier", password="test-password", is_staff=True
    )
    store = POSLocation.objects.create(code="MAIN", name="Main Store")
    terminal = POSTerminal.objects.create(
        location=store, code="MAIN-01", name="POS 1"
    )
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=store)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    rice = Product.objects.create(
        sku="DEMO-RICE-001", name="Demo Rice 1kg",
        currency="NGN", unit_price_minor=350000
    )
    inventory = InventoryItem.objects.create(
        product=rice, location_code="MAIN", quantity=20
    )
    client = Client()
    client.force_login(user)

    scope = client.get("/api/transactional/pos/scope/")
    assert scope.status_code == 200
    assert scope.json()["locations"][0]["code"] == "MAIN"
    assert scope.json()["locations"][0]["terminals"][0]["code"] == "MAIN-01"

    query = {"location_code": "MAIN", "terminal_code": "MAIN-01", "q": "Rice"}
    catalog = client.get("/api/transactional/pos/catalog/", query)
    assert catalog.status_code == 200
    assert catalog.json()["products"][0]["stock"] == 20
    assert catalog.json()["products"][0]["unit_price_minor"] == 350000

    payload = {
        "lines": [{"product_id": rice.pk, "quantity": 2}],
        "location_code": "MAIN",
        "terminal_code": "MAIN-01",
        "currency": "NGN",
        "amount_minor": 700000,
        "sale_idempotency_key": "e2e-sale-001",
        "payment_idempotency_key": "e2e-payment-001",
        "provider_reference": "E2E-CASH-001",
    }
    path = "/api/transactional/pos/sales/"
    first = client.post(path, data=json.dumps(payload), content_type="application/json")
    retry = client.post(path, data=json.dumps(payload), content_type="application/json")
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    result = first.json()
    assert result["total_minor"] == 700000
    assert result["sale_status"] == Sale.Status.COMPLETED
    assert result["payment_status"] == Payment.Status.SUCCEEDED

    inventory.refresh_from_db()
    assert inventory.quantity == 18
    assert Sale.objects.count() == 1
    assert SaleLine.objects.count() == 1
    assert Payment.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    movement = InventoryMovement.objects.get()
    assert movement.quantity_delta == -2
    assert movement.reason == InventoryMovement.Reason.SALE
    payment = Payment.objects.get()
    assert payment.method == Payment.Method.CASH
    assert payment.amount_minor == 700000
    assert payment.sale_id == result["sale_id"]

    receipt = client.get(
        f"/api/transactional/pos/sales/{result['sale_id']}/receipt/", query
    )
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["reference"] == result["reference"]
    assert body["total_minor"] == 700000
    assert body["currency"] == "NGN"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["name"] == "Demo Rice 1kg"
    assert body["lines"][0]["quantity"] == 2
    assert body["lines"][0]["line_total_minor"] == 700000
    assert len(body["payments"]) == 1
    assert body["payments"][0]["amount_minor"] == 700000
    assert body["payments"][0]["status"] == Payment.Status.SUCCEEDED

    refreshed_catalog = client.get("/api/transactional/pos/catalog/", query)
    assert refreshed_catalog.json()["products"][0]["stock"] == 18


@pytest.mark.django_db
def test_receipt_cannot_be_read_by_anonymous_user():
    response = Client().get(
        "/api/transactional/pos/sales/123/receipt/",
        {"location_code": "MAIN", "terminal_code": "MAIN-01"},
    )
    assert response.status_code in (401, 403)
