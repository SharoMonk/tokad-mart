"""Stocktaking report and stale-count protections."""
import json
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    InventoryItem, InventoryMovement, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal, Product, StockOperation,
)


@pytest.fixture
def stocktake_setup(db):
    location = POSLocation.objects.create(code="COUNT", name="Count shop")
    terminal = POSTerminal.objects.create(location=location, code="TERM", name="Count terminal")
    clients = []
    for name, role in (
        ("count-manager", POSOperator.Role.SUPERVISOR),
        ("count-cashier", POSOperator.Role.OPERATOR),
    ):
        user = get_user_model().objects.create_user(name, password="test", is_staff=True)
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        client = Client()
        client.force_login(user)
        clients.append(client)
    rice = Product.objects.create(sku="COUNT-RICE", name="Rice", unit_price_minor=10000)
    soap = Product.objects.create(sku="COUNT-SOAP", name="Soap", unit_price_minor=20000)
    InventoryItem.objects.create(product=rice, location_code="COUNT", quantity=4)
    return clients[0], clients[1], rice, soap


def report(client, **kwargs):
    return client.get("/api/transactional/pos/manage/inventory-report/", {
        "location_code": "COUNT", "terminal_code": "TERM",
        "threshold": "5", "mode": "all", **kwargs
    })


def adjust(client, **kwargs):
    data = {
        "location_code": "COUNT", "terminal_code": "TERM",
        "sku": "COUNT-RICE", "operation": "ADJUST", "quantity": -1,
        "expected_quantity": 4,
        "reference": "count-sheet-001", "notes": "Physical verification",
        "idempotency_key": "count-" + str(uuid4()), **kwargs,
    }
    return client.post(
        "/api/transactional/pos/manage/stock/",
        json.dumps(data), content_type="application/json",
    )


@pytest.mark.django_db
def test_report_lists_zero_stock_and_low_stock_in_scope(stocktake_setup):
    supervisor, cashier, rice, soap = stocktake_setup
    assert report(cashier).status_code == 403
    assert report(Client()).status_code in (401, 403)
    assert report(supervisor, location_code="OTHER").status_code == 403
    response = report(supervisor)
    assert response.status_code == 200
    rows = {item["sku"]: item for item in response.json()["products"]}
    assert rows["COUNT-RICE"]["current_stock"] == 4
    assert rows["COUNT-SOAP"]["current_stock"] == 0
    assert all(item["low_stock"] for item in rows.values())
    assert len(report(supervisor, mode="low").json()["products"]) == 2
    assert report(supervisor, threshold="not-a-number").status_code == 400


@pytest.mark.django_db
def test_stocktake_rejects_stale_baseline_without_writing_movement(stocktake_setup):
    supervisor, _, rice, _ = stocktake_setup
    first = adjust(supervisor)
    assert first.status_code == 201, first.content
    assert first.json()["quantity_after"] == 3
    stale = adjust(supervisor, expected_quantity=4)
    assert stale.status_code == 409
    assert stale.json()["error"] == "stock_changed_since_count"
    assert stale.json()["current_quantity"] == 3
    stock = InventoryItem.objects.get(product=rice, location_code="COUNT")
    assert stock.quantity == 3
    assert InventoryMovement.objects.filter(inventory_item=stock).count() == 1
    assert StockOperation.objects.count() == 1
    corrected = adjust(supervisor, expected_quantity=3, quantity=-2)
    assert corrected.status_code == 201, corrected.content
    stock.refresh_from_db()
    assert stock.quantity == 1


@pytest.mark.django_db
def test_stocktake_key_replay_does_not_reconcile_twice(stocktake_setup):
    supervisor, _, rice, _ = stocktake_setup
    key = "count-retry-" + str(uuid4())
    response = adjust(supervisor, idempotency_key=key)
    assert response.status_code == 201
    replay = adjust(supervisor, idempotency_key=key)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert adjust(supervisor, idempotency_key=key, quantity=-2).status_code == 409
    assert InventoryItem.objects.get(product=rice, location_code="COUNT").quantity == 3
