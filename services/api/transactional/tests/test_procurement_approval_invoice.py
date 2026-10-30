"""PO approval and supplier invoice matching authorization and ledger invariants."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    GoodsReceipt, InventoryItem, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal,
    Product, PurchaseOrder, PurchaseOrderApproval, PurchaseOrderLine,
    Supplier, SupplierInvoice,
)


@pytest.fixture
def procurement_clients(db):
    location = POSLocation.objects.create(code="AP", name="AP location")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="Terminal")
    clients = []
    for name, role in [
        ("ap-creator", POSOperator.Role.SUPERVISOR),
        ("ap-approver", POSOperator.Role.SUPERVISOR),
        ("ap-cashier", POSOperator.Role.OPERATOR),
    ]:
        user = get_user_model().objects.create_user(name, password="test", is_staff=True)
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        client = Client()
        client.force_login(user)
        clients.append(client)
    Supplier.objects.create(code="AP-SUP", name="Supplier")
    product = Product.objects.create(sku="AP-RICE", name="Rice", unit_price_minor=40000)
    order = PurchaseOrder.objects.create(
        reference="AP-PO-1", supplier=Supplier.objects.get(code="AP-SUP"),
        location=location, created_by=POSOperator.objects.get(user__username="ap-creator"),
    )
    line = PurchaseOrderLine.objects.create(
        order=order, product=product, quantity_ordered=10, unit_cost_minor=25000,
    )
    return clients, order, line


def post(client, path, data):
    return client.post(path, json.dumps(data), content_type="application/json")


def payload(**kwargs):
    return {"location_code": "AP", "terminal_code": "T1", **kwargs}


@pytest.mark.django_db
def test_two_person_approval_and_receipt_gate(procurement_clients):
    (creator, approver, cashier), order, line = procurement_clients
    approve_url = f"/api/transactional/pos/manage/purchase-orders/{order.id}/approve/"
    receive_url = f"/api/transactional/pos/manage/purchase-orders/{order.id}/receive/"
    receipt_payload = payload(
        reference="DN-1", idempotency_key="receipt-ap-test-1",
        lines=[{"line_id": line.pk, "quantity": 4}],
    )
    assert post(creator, receive_url, receipt_payload).status_code == 409
    assert post(cashier, approve_url, payload(note="Reviewed")).status_code == 403
    assert post(creator, approve_url, payload(note="Self approval")).status_code == 403
    approved = post(approver, approve_url, payload(note="Approved after checking supplier"))
    assert approved.status_code == 201, approved.content
    assert PurchaseOrderApproval.objects.filter(order=order).count() == 1
    assert post(approver, approve_url, payload(note="Again")).status_code == 409
    received = post(creator, receive_url, receipt_payload)
    assert received.status_code == 201, received.content
    assert InventoryItem.objects.get(product=line.product, location_code="AP").quantity == 4
    return_value = received.json()
    assert return_value["receipt_id"]


@pytest.mark.django_db
def test_invoice_three_way_quantity_price_amount_matching_and_ap_report(procurement_clients):
    (creator, approver, cashier), order, line = procurement_clients
    assert post(
        approver,
        f"/api/transactional/pos/manage/purchase-orders/{order.id}/approve/",
        payload(note="Checked"),
    ).status_code == 201
    delivery = post(
        creator, f"/api/transactional/pos/manage/purchase-orders/{order.id}/receive/",
        payload(reference="DN-2", idempotency_key="receipt-ap-test-2",
                lines=[{"line_id": line.pk, "quantity": 4}]),
    )
    assert delivery.status_code == 201, delivery.content
    url = "/api/transactional/pos/manage/supplier-invoices/"
    invoice = payload(
        receipt_id=delivery.json()["receipt_id"],
        number="INV-100", amount_minor=100000,
        notes="Invoice agrees to four units at 250 naira",
    )
    assert post(cashier, url, invoice).status_code == 403
    matched = post(creator, url, invoice)
    assert matched.status_code == 201, matched.content
    assert matched.json()["status"] == "MATCHED"
    assert matched.json()["expected_minor"] == 100000
    assert post(creator, url, invoice).status_code == 409
    assert SupplierInvoice.objects.count() == 1
    ap = creator.get("/api/transactional/pos/manage/accounts-payable/", payload())
    assert ap.status_code == 200
    assert ap.json()["matched_unpaid_or_unverified_minor"] == 100000
    assert ap.json()["rows"][0]["payment_status"] == "NOT_TRACKED"


@pytest.mark.django_db
def test_invoice_amount_difference_is_exception_not_matched_liability(procurement_clients):
    (creator, approver, cashier), order, line = procurement_clients
    assert post(
        approver, f"/api/transactional/pos/manage/purchase-orders/{order.id}/approve/",
        payload(note="Checked"),
    ).status_code == 201
    receipt = post(
        creator, f"/api/transactional/pos/manage/purchase-orders/{order.id}/receive/",
        payload(reference="DN-3", idempotency_key="receipt-ap-test-3",
                lines=[{"line_id": line.pk, "quantity": 2}]),
    )
    assert receipt.status_code == 201
    invoice = post(
        creator, "/api/transactional/pos/manage/supplier-invoices/",
        payload(receipt_id=receipt.json()["receipt_id"], number="INV-EX",
                amount_minor=55000, notes="Variance under investigation"),
    )
    assert invoice.status_code == 201
    assert invoice.json()["status"] == "EXCEPTION"
    assert invoice.json()["expected_minor"] == 50000
    ap = creator.get("/api/transactional/pos/manage/accounts-payable/", payload()).json()
    assert ap["matched_unpaid_or_unverified_minor"] == 0
    assert ap["exception_minor"] == 55000
