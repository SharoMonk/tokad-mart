"""Second-person PO approval, goods-receipt invoice matching and AP register.

No bank transfer or payment record is created by this module.
"""
from django.db import IntegrityError, transaction
from django.db.models import Sum, F
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import (
    AuditEvent, GoodsReceipt, POSOperator, PurchaseOrder,
    PurchaseOrderApproval, SupplierInvoice,
)
from .permissions import IsPOSOperator
from .supervisor_procurement_api import fail, parse_body, scope_for, valid_text


def _approved(order):
    return PurchaseOrderApproval.objects.filter(order_id=order.pk).exists()


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def approve_purchase_order(request, order_id):
    data = parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    note = data.get("note")
    if not valid_text(note, 500):
        return fail("approval_note_required")
    with transaction.atomic():
        order = PurchaseOrder.objects.select_for_update().filter(
            pk=order_id, location=scope.location
        ).first()
        if order is None:
            return fail("order_not_found", 404)
        if order.created_by_id == scope.operator.pk:
            return fail("self_approval_forbidden", 403)
        approval = PurchaseOrderApproval.objects.filter(order=order).first()
        if approval:
            return fail("already_approved", 409)
        if GoodsReceipt.objects.filter(order=order).exists():
            return fail("historical_receipts_require_review", 409)
        PurchaseOrderApproval.objects.create(
            order=order, approved_by=scope.operator, note=note,
        )
        AuditEvent.objects.create(
            actor=str(request.user.pk), action="purchase_order.approved",
            entity_type="PurchaseOrder", entity_reference=str(order.pk),
            metadata={"note": note, "location_code": scope.location.code},
        )
    return JsonResponse({"order_id": order_id, "approval": "APPROVED"}, status=201)


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supplier_invoices(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        invoices = SupplierInvoice.objects.filter(
            receipt__order__location=scope.location
        ).select_related("supplier", "receipt", "receipt__order").order_by("-id")[:100]
        return JsonResponse({"invoices": [{
            "id": invoice.pk, "number": invoice.number,
            "supplier_code": invoice.supplier.code,
            "purchase_order": invoice.receipt.order.reference,
            "receipt_reference": invoice.receipt.reference,
            "amount_minor": invoice.amount_minor,
            "expected_minor": invoice.expected_minor,
            "status": invoice.status,
        } for invoice in invoices]})
    receipt_id, number, amount, notes = (
        data.get("receipt_id"), data.get("number"),
        data.get("amount_minor"), data.get("notes"),
    )
    if type(receipt_id) is not int or receipt_id <= 0:
        return fail("invalid_receipt")
    if not valid_text(number, 128):
        return fail("invalid_invoice_number")
    if type(amount) is not int or amount <= 0 or amount > 10**15:
        return fail("invalid_invoice_amount")
    if not valid_text(notes, 1000):
        return fail("invoice_notes_required")
    try:
        with transaction.atomic():
            receipt = GoodsReceipt.objects.select_related(
                "order", "order__supplier"
            ).filter(pk=receipt_id, order__location=scope.location).first()
            if receipt is None:
                return fail("receipt_not_found", 404)
            order = PurchaseOrder.objects.select_for_update().get(pk=receipt.order_id)
            if not _approved(order):
                return fail("unapproved_purchase_order", 409)
            if SupplierInvoice.objects.filter(receipt=receipt).exists():
                return fail("receipt_already_invoiced", 409)
            expected = sum(
                row.quantity * row.order_line.unit_cost_minor
                for row in receipt.lines.select_related("order_line")
            )
            status = (
                SupplierInvoice.Status.MATCHED if amount == expected
                else SupplierInvoice.Status.EXCEPTION
            )
            invoice = SupplierInvoice.objects.create(
                supplier=order.supplier, receipt=receipt, number=number,
                amount_minor=amount, expected_minor=expected,
                status=status, notes=notes, recorded_by=scope.operator,
            )
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="supplier_invoice.recorded",
                entity_type="SupplierInvoice", entity_reference=str(invoice.pk),
                metadata={
                    "order_id": order.pk, "receipt_id": receipt.pk,
                    "amount_minor": amount, "expected_minor": expected,
                    "status": status, "location_code": scope.location.code,
                },
            )
    except IntegrityError:
        return fail("supplier_invoice_conflict", 409)
    return JsonResponse({
        "id": invoice.pk, "status": status, "expected_minor": expected,
        "amount_minor": amount,
    }, status=201)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def accounts_payable_register(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    invoices = SupplierInvoice.objects.filter(
        receipt__order__location=scope.location
    ).select_related("supplier").order_by("-id")[:200]
    rows = [{
        "id": item.pk, "number": item.number, "supplier_code": item.supplier.code,
        "amount_minor": item.amount_minor, "expected_minor": item.expected_minor,
        "status": item.status,
        "payment_status": "NOT_TRACKED",
    } for item in invoices]
    return JsonResponse({
        "currency": "NGN", "rows": rows,
        "matched_unpaid_or_unverified_minor": sum(
            row["amount_minor"] for row in rows if row["status"] == "MATCHED"
        ),
        "exception_minor": sum(
            row["amount_minor"] for row in rows if row["status"] == "EXCEPTION"
        ),
        "note": "Amounts are recorded invoice exposure, not verified unpaid liabilities. Supplier payment posting is not implemented.",
    })
