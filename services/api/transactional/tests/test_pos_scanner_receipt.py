"""Receipt and keyboard-wedge scanner API contract.

A USB keyboard-wedge scanner types a code and Return into the dedicated
frontend input. The existing catalog API must return matching SKU values
and the receipt must remain an authoritative record after checkout.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product,
)


@pytest.mark.django_db
def test_sku_search_and_receipt_remain_linked_to_completed_cash_sale():
    cashier = get_user_model().objects.create_user(
        username="scanner-cashier", password="test-password", is_staff=True,
    )
    location = POSLocation.objects.create(code="SCAN", name="Scanner store")
    terminal = POSTerminal.objects.create(
        location=location, code="SCAN-01", name="Register",
    )
    operator = POSOperator.objects.create(user=cashier)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    product = Product.objects.create(
        sku="8901234567890", name="Scanner test soap",
        unit_price_minor=85000, currency="NGN",
    )
    stock = InventoryItem.objects.create(
        product=product, location_code="SCAN", quantity=5,
    )
    client = Client()
    client.force_login(cashier)

    params = {
        "location_code": "SCAN", "terminal_code": "SCAN-01",
        "q": "8901234567890",
    }
    result = client.get("/api/transactional/pos/catalog/", params)
    assert result.status_code == 200
    assert [(p["sku"], p["stock"]) for p in result.json()["products"]] == [
        ("8901234567890", 5),
    ]

    opened = client.post(
        "/api/transactional/pos/shifts/",
        json.dumps({
            "location_code": "SCAN", "terminal_code": "SCAN-01",
            "opening_cash_minor": 0,
        }),
        content_type="application/json",
    )
    assert opened.status_code == 201
    shift_id = opened.json()["shift"]["id"]

    sale = client.post(
        "/api/transactional/pos/shift-sales/",
        json.dumps({
            "location_code": "SCAN", "terminal_code": "SCAN-01",
            "shift_id": shift_id,
            "currency": "NGN",
            "lines": [{"product_id": product.id, "quantity": 1}],
            "amount_minor": 85000,
            "sale_idempotency_key": "scanner-sale-1",
            "payment_idempotency_key": "scanner-payment-1",
            "provider_reference": "scanner-cash-1",
        }),
        content_type="application/json",
    )
    assert sale.status_code == 201
    detail = sale.json()
    receipt = client.get(
        f"/api/transactional/pos/sales/{detail['sale_id']}/receipt/",
        {"location_code": "SCAN", "terminal_code": "SCAN-01"},
    )
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["reference"] == detail["reference"]
    assert body["total_minor"] == 85000
    assert body["lines"][0]["sku"] == "8901234567890"
    assert body["lines"][0]["name"] == "Scanner test soap"
    assert body["lines"][0]["quantity"] == 1
    assert body["payments"][0]["status"] == "SUCCEEDED"
    stock.refresh_from_db()
    assert stock.quantity == 4
    assert client.get("/api/transactional/pos/catalog/", params).json()["products"][0]["stock"] == 4
