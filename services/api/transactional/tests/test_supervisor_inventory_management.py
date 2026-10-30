"""Stock movements preserve quantity, idempotency, authorization and audit."""
import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    AuditEvent, InventoryItem, InventoryMovement, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal, Product, StockOperation,
)


@pytest.fixture
def inventory_users(db):
    location = POSLocation.objects.create(code="INV", name="Inventory")
    terminal = POSTerminal.objects.create(location=location, code="INV-1", name="Register")
    users = []
    for name, role in (
        ("receiving-supervisor", POSOperator.Role.SUPERVISOR),
        ("receiving-cashier", POSOperator.Role.OPERATOR),
    ):
        user = get_user_model().objects.create_user(name, password="test", is_staff=True)
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        users.append(user)
    product = Product.objects.create(
        sku="INV-RICE", name="Rice", currency="NGN", unit_price_minor=50000
    )
    return users[0], users[1], product


def payload(**changes):
    return {
        "location_code": "INV", "terminal_code": "INV-1",
        "sku": "INV-RICE", "operation": "RECEIVE",
        "quantity": 20, "reference": "supplier-invoice-100",
        "notes": "Twenty units counted and received",
        "idempotency_key": "receiving-" + str(uuid.uuid4()),
        **changes,
    }


def send(client, data):
    return client.post(
        "/api/transactional/pos/manage/stock/",
        json.dumps(data), content_type="application/json",
    )


@pytest.mark.django_db
def test_receiving_idempotent_and_records_exactly_one_movement(inventory_users):
    manager, cashier, product = inventory_users
    client = Client()
    request = payload()
    client.force_login(cashier)
    assert send(client, request).status_code == 403
    assert not InventoryItem.objects.filter(product=product).exists()
    client.force_login(manager)
    first = send(client, request)
    assert first.status_code == 201, first.content
    assert first.json()["quantity_after"] == 20
    second = send(client, request)
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["movement_id"] == first.json()["movement_id"]
    assert send(client, {**request, "quantity": 21}).status_code == 409
    stock = InventoryItem.objects.get(product=product, location_code="INV")
    assert stock.quantity == 20
    assert InventoryMovement.objects.filter(inventory_item=stock).count() == 1
    assert StockOperation.objects.count() == 1
    assert AuditEvent.objects.filter(action="inventory.received").count() == 1


@pytest.mark.django_db
def test_adjustment_cannot_overdraw_or_mutate_stock_on_error(inventory_users):
    manager, _, product = inventory_users
    client = Client()
    client.force_login(manager)
    assert send(client, payload(quantity=-1)).status_code == 400
    assert send(client, payload(operation="ADJUST", quantity=-1)).status_code == 409
    stock = InventoryItem.objects.get(product=product, location_code="INV")
    assert stock.quantity == 0
    assert InventoryMovement.objects.count() == 0
    assert send(client, payload()).status_code == 201
    result = send(client, payload(
        operation="ADJUST", quantity=-3,
        reference="stocktake-1", notes="Three damaged items",
    ))
    assert result.status_code == 201, result.content
    assert result.json()["quantity_after"] == 17
    stock.refresh_from_db()
    assert stock.quantity == 17
    movement = InventoryMovement.objects.order_by("-id").first()
    assert movement.reason == InventoryMovement.Reason.ADJUSTMENT
    assert movement.quantity_delta == -3


@pytest.mark.django_db
def test_invalid_scope_and_requests_do_not_create_movements(inventory_users):
    manager, _, product = inventory_users
    client = Client()
    client.force_login(manager)
    assert send(client, payload(location_code="OTHER")).status_code == 403
    assert send(client, payload(quantity=True)).status_code == 400
    assert send(client, payload(notes="")).status_code == 400
    assert send(client, payload(sku="UNKNOWN")).status_code == 404
    assert InventoryMovement.objects.count() == 0
    assert StockOperation.objects.count() == 0
