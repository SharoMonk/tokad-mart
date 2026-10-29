"""Procurement integration: scope, partial receipts, ledger, replay and replenishment."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    AuditEvent, GoodsReceipt, GoodsReceiptLine, InventoryItem, InventoryMovement,
    POSLocation, POSOperator, POSOperatorLocation, POSOperatorTerminal, POSTerminal,
    Product, PurchaseOrder, PurchaseOrderLine, Supplier,
)


@pytest.fixture
def users(db):
    location = POSLocation.objects.create(code="PROC", name="Procurement")
    terminal = POSTerminal.objects.create(location=location, code="P1", name="Till")
    clients = []
    for username, role in (
        ("proc-supervisor", POSOperator.Role.SUPERVISOR),
        ("proc-cashier", POSOperator.Role.OPERATOR),
        ("proc-approver", POSOperator.Role.SUPERVISOR),
    ):
        user = get_user_model().objects.create_user(
            username, password="example", is_staff=True,
        )
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        client = Client()
        client.force_login(user)
        clients.append(client)
    Product.objects.create(sku="PR-RICE", name="Rice", unit_price_minor=50000)
    Product.objects.create(sku="PR-SOAP", name="Soap", unit_price_minor=25000)
    return clients


def post(client, path, data):
    return client.post(path, json.dumps(data), content_type="application/json")


def scoped(**kwargs):
    return {"location_code": "PROC", "terminal_code": "P1", **kwargs}


def initialize(client, approver):
    supplier = post(client, "/api/transactional/pos/manage/suppliers/", scoped(
        code="SUP-ONE", name="First Supplier", contact="012345",
    ))
    assert supplier.status_code == 201, supplier.content
    order = post(client, "/api/transactional/pos/manage/purchase-orders/", scoped(
        reference="PO-100", supplier_code="SUP-ONE",
        lines=[
            {"sku": "PR-RICE", "quantity": 10, "unit_cost_minor": 30000},
            {"sku": "PR-SOAP", "quantity": 4, "unit_cost_minor": 12000},
        ],
    ))
    assert order.status_code == 201, order.content
    created = order.json()["order"]
    approval = post(approver, f"/api/transactional/pos/manage/purchase-orders/{created[\'id\']}/approve/", scoped(note="Reviewed purchase order and pricing"))
    assert approval.status_code == 201, approval.content
    return created


@pytest.mark.django_db
def test_supervisor_only_supplier_and_po_creation(users):
    manager, cashier, approver = users
    suppliers_url = "/api/transactional/pos/manage/suppliers/"
    assert post(cashier, suppliers_url, scoped(code="X", name="No")).status_code == 403
    assert post(manager, suppliers_url, scoped(
        location_code="WRONG", code="X", name="No"
    )).status_code == 403
    assert post(manager, suppliers_url, scoped(
        code="SUP-ONE", name="First Supplier"
    )).status_code == 201
    assert post(manager, suppliers_url, scoped(
        code="SUP-ONE", name="Duplicate"
    )).status_code == 409
    assert Supplier.objects.count() == 1
    bad_order = post(manager, "/api/transactional/pos/manage/purchase-orders/", scoped(
        reference="PO-WRONG", supplier_code="SUP-ONE",
        lines=[{"sku": "UNKNOWN", "quantity": 4, "unit_cost_minor": 100}],
    ))
    assert bad_order.status_code == 404
    assert PurchaseOrder.objects.count() == 0


@pytest.mark.django_db
def test_partial_receipts_post_to_canonical_inventory_once(users):
    manager, cashier, approver = users
    order = initialize(manager, approver)
    url = f"/api/transactional/pos/manage/purchase-orders/{order['id']}/receive/"
    rice, soap = order["lines"]
    request = scoped(
        reference="GRN-1", idempotency_key="receipt-test-grn-1",
        lines=[{"line_id": rice["id"], "quantity": 3}],
    )
    assert post(cashier, url, request).status_code == 403
    first = post(manager, url, request)
    assert first.status_code == 201, first.content
    assert first.json()["order"]["status"] == "PARTIAL"
    retry = post(manager, url, request)
    assert retry.status_code == 200
    assert retry.json()["replayed"] is True
    assert post(manager, url, {**request, "reference": "GRN-OTHER"}).status_code == 409
    assert post(manager, url, scoped(
        reference="GRN-BAD", idempotency_key="receipt-test-excess",
        lines=[{"line_id": rice["id"], "quantity": 8}],
    )).status_code == 409
    assert PurchaseOrderLine.objects.get(pk=rice["id"]).quantity_received == 3
    assert InventoryItem.objects.get(
        product__sku="PR-RICE", location_code="PROC"
    ).quantity == 3
    assert InventoryMovement.objects.count() == 1
    assert GoodsReceipt.objects.count() == 1
    assert GoodsReceiptLine.objects.count() == 1

    second = post(manager, url, scoped(
        reference="GRN-2", idempotency_key="receipt-test-grn-2",
        lines=[
            {"line_id": rice["id"], "quantity": 7},
            {"line_id": soap["id"], "quantity": 4},
        ],
    ))
    assert second.status_code == 201, second.content
    assert second.json()["order"]["status"] == "RECEIVED"
    assert InventoryItem.objects.get(
        product__sku="PR-RICE", location_code="PROC"
    ).quantity == 10
    assert InventoryItem.objects.get(
        product__sku="PR-SOAP", location_code="PROC"
    ).quantity == 4
    assert InventoryMovement.objects.filter(
        reason=InventoryMovement.Reason.PURCHASE
    ).count() == 3
    assert AuditEvent.objects.filter(
        action="purchase_order.goods_received"
    ).count() == 3


@pytest.mark.django_db
def test_replenishment_reflects_on_order_and_received_quantities(users):
    manager, cashier, approver = users
    order = initialize(manager, approver)
    url = "/api/transactional/pos/manage/replenishment/"
    params = scoped(threshold="5")
    assert cashier.get(url, params).status_code == 403
    response = manager.get(url, params)
    assert response.status_code == 200
    rows = {row["sku"]: row for row in response.json()["products"]}
    assert rows["PR-RICE"]["current_stock"] == 0
    assert rows["PR-RICE"]["outstanding_order_units"] == 10
    assert rows["PR-RICE"]["reorder_gap_units"] == 0
    assert rows["PR-SOAP"]["outstanding_order_units"] == 4
    assert rows["PR-SOAP"]["reorder_gap_units"] == 2

    detail_url = f"/api/transactional/pos/manage/purchase-orders/{order['id']}/"
    assert manager.get(detail_url, scoped()).json()["order"]["status"] == "OPEN"
    first_line = order["lines"][0]
    receipt_url = detail_url + "receive/"
    assert post(manager, receipt_url, scoped(
        reference="GRN-1", idempotency_key="replenishment-receipt",
        lines=[{"line_id": first_line["id"], "quantity": 3}],
    )).status_code == 201
    rows = {
        row["sku"]: row for row in manager.get(url, params).json()["products"]
    }
    assert rows["PR-RICE"]["current_stock"] == 3
    assert rows["PR-RICE"]["outstanding_order_units"] == 7
    assert rows["PR-RICE"]["reorder_gap_units"] == 0
    assert manager.get(url, scoped(threshold="bad")).status_code == 400
