"""Supplier payment evidence: no bank movement, scoped review, no overpayment."""
import json
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    GoodsReceipt, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product, PurchaseOrder,
    PurchaseOrderLine, GoodsReceiptLine, InventoryItem, InventoryMovement,
    Supplier, SupplierInvoice, SupplierPaymentEvidence, AuditEvent,
)


@pytest.fixture
def ap_scope(db):
    location = POSLocation.objects.create(code="FIN", name="Finance")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="Till")
    clients = []
    operators = []
    for username, role in [
        ("finance-recorder", POSOperator.Role.SUPERVISOR),
        ("finance-verifier", POSOperator.Role.SUPERVISOR),
        ("finance-cashier", POSOperator.Role.OPERATOR),
    ]:
        user = get_user_model().objects.create_user(username, password="test", is_staff=True)
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        client = Client()
        client.force_login(user)
        clients.append(client)
        operators.append(operator)
    supplier = Supplier.objects.create(code="FIN-SUP", name="Supplier")
    product = Product.objects.create(sku="FIN-RICE", name="Rice", unit_price_minor=20000)
    order = PurchaseOrder.objects.create(
        supplier=supplier, reference="FIN-PO", location=location, created_by=operators[0]
    )
    line = PurchaseOrderLine.objects.create(
        order=order, product=product, quantity_ordered=4, quantity_received=4,
        unit_cost_minor=25000,
    )
    inventory = InventoryItem.objects.create(product=product, location_code="FIN", quantity=4)
    movement = InventoryMovement.objects.create(
        inventory_item=inventory, quantity_delta=4,
        reason=InventoryMovement.Reason.PURCHASE, reference="FIN-PO/GRN-1",
    )
    receipt = GoodsReceipt.objects.create(
        order=order, reference="GRN-1", key="fin-receipt-key",
        request_fingerprint="a" * 64, received_by=operators[0],
    )
    GoodsReceiptLine.objects.create(
        receipt=receipt, order_line=line, quantity=4, movement=movement,
    )
    invoice = SupplierInvoice.objects.create(
        supplier=supplier, receipt=receipt, number="FIN-INV",
        amount_minor=100000, expected_minor=100000,
        status=SupplierInvoice.Status.MATCHED,
        notes="Matched", recorded_by=operators[0],
    )
    exception = SupplierInvoice.objects.create(
        supplier=supplier,
        receipt=GoodsReceipt.objects.create(
            order=order, reference="GRN-2", key="fin-receipt-key-2",
            request_fingerprint="b" * 64, received_by=operators[0],
        ),
        number="FIN-EX", amount_minor=15000, expected_minor=10000,
        status=SupplierInvoice.Status.EXCEPTION, notes="Mismatch",
        recorded_by=operators[0],
    )
    return clients, invoice, exception


def body(**kwargs):
    return {"location_code": "FIN", "terminal_code": "T1", **kwargs}


def post(client, path, payload):
    return client.post(path, json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_evidence_is_idempotent_cannot_overpay_or_post_exception(ap_scope):
    (recorder, verifier, cashier), invoice, exception = ap_scope
    url = "/api/transactional/pos/manage/supplier-payments/"
    payload = body(
        invoice_id=invoice.pk, reference="BANK-REF-01",
        idempotency_key="payment-fin-01", amount_minor=60000,
        notes="Reviewed bank statement line",
    )
    assert post(cashier, url, payload).status_code == 403
    first = post(recorder, url, payload)
    assert first.status_code == 201, first.content
    assert first.json()["payment"]["status"] == "RECORDED"
    assert post(recorder, url, payload).json()["replayed"] is True
    assert post(recorder, url, {**payload, "amount_minor": 61000}).status_code == 409
    assert post(recorder, url, body(
        invoice_id=invoice.pk, reference="BANK-REF-02",
        idempotency_key="payment-fin-02", amount_minor=50000,
        notes="Overpayment attempt",
    )).status_code == 409
    assert post(recorder, url, body(
        invoice_id=exception.pk, reference="BANK-EX",
        idempotency_key="payment-exception", amount_minor=1000,
        notes="Exception cannot settle",
    )).status_code == 409
    assert SupplierPaymentEvidence.objects.count() == 1
    assert AuditEvent.objects.filter(action="supplier_payment.recorded").count() == 1


@pytest.mark.django_db
def test_independent_verification_and_reconciliation(ap_scope):
    (recorder, verifier, cashier), invoice, exception = ap_scope
    url = "/api/transactional/pos/manage/supplier-payments/"
    payment = post(recorder, url, body(
        invoice_id=invoice.pk, reference="BANK-REF-11",
        idempotency_key="payment-fin-11", amount_minor=40000,
        notes="External transfer confirmation",
    ))
    assert payment.status_code == 201
    payment_id = payment.json()["payment"]["id"]
    verify_url = f"{url}{payment_id}/verify/"
    review = body(notes="Independently reviewed external confirmation")
    assert post(recorder, verify_url, review).status_code == 403
    assert post(cashier, verify_url, review).status_code == 403
    report_url = "/api/transactional/pos/manage/supplier-reconciliation/"
    before = recorder.get(report_url, body()).json()["rows"]
    before_row = next(row for row in before if row["invoice_id"] == invoice.pk)
    assert before_row["pending_review_minor"] == 40000
    assert before_row["verified_evidence_minor"] == 0
    success = post(verifier, verify_url, review)
    assert success.status_code == 200, success.content
    assert post(verifier, verify_url, review).status_code == 409
    after = recorder.get(report_url, body()).json()["rows"]
    row = next(item for item in after if item["invoice_id"] == invoice.pk)
    assert row["verified_evidence_minor"] == 40000
    assert row["remaining_unverified_minor"] == 60000
    assert row["review_status"] == "PARTIAL"
    assert next(item for item in after if item["invoice_id"] == exception.pk)["review_status"] == "EXCEPTION"
    assert AuditEvent.objects.filter(action="supplier_payment.verified").count() == 1
