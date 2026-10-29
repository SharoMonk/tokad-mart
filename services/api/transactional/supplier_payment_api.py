"""Manual supplier payment evidence, two-person verification, and reconciliation.

Verification means a different supervisor reviewed external evidence. It is NOT
a bank API confirmation, bank transfer, or posting to the general ledger.
"""
import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import AuditEvent, SupplierInvoice, SupplierPaymentEvidence
from .permissions import IsPOSOperator
from .supervisor_procurement_api import fail, parse_body, scope_for, valid_text


def _row(payment):
    return {
        "id": payment.pk,
        "invoice_id": payment.invoice_id,
        "reference": payment.reference,
        "amount_minor": payment.amount_minor,
        "status": payment.status,
        "recorded_at": payment.recorded_at.isoformat(),
        "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
    }


def _fingerprint(invoice_id, reference, amount, notes):
    value = json.dumps(
        [invoice_id, reference, amount, notes], separators=(",", ":")
    ).encode()
    return hashlib.sha256(value).hexdigest()


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supplier_payment_evidence(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        records = SupplierPaymentEvidence.objects.filter(
            invoice__receipt__order__location=scope.location
        ).order_by("-id")[:100]
        return JsonResponse({"payments": [_row(p) for p in records]})
    invoice_id, reference, key, amount, notes = (
        data.get("invoice_id"), data.get("reference"),
        data.get("idempotency_key"), data.get("amount_minor"), data.get("notes")
    )
    if type(invoice_id) is not int or invoice_id < 1:
        return fail("invalid_invoice_id")
    if not valid_text(reference, 128) or not valid_text(key, 128) or len(key) < 8:
        return fail("invalid_reference_or_key")
    if type(amount) is not int or not (1 <= amount <= 10**15):
        return fail("invalid_amount")
    if not valid_text(notes, 1000):
        return fail("payment_evidence_notes_required")
    digest = _fingerprint(invoice_id, reference, amount, notes)
    try:
        with transaction.atomic():
            invoice = SupplierInvoice.objects.select_for_update().filter(
                pk=invoice_id, receipt__order__location=scope.location
            ).first()
            if invoice is None:
                return fail("invoice_not_found", 404)
            previous = SupplierPaymentEvidence.objects.filter(idempotency_key=key).first()
            if previous:
                if previous.invoice_id != invoice.pk or previous.fingerprint != digest:
                    return fail("idempotency_conflict", 409)
                return JsonResponse({"payment": _row(previous), "replayed": True})
            if invoice.status != SupplierInvoice.Status.MATCHED:
                return fail("invoice_exception_unresolved", 409)
            if SupplierPaymentEvidence.objects.filter(reference=reference).exists():
                return fail("payment_reference_exists", 409)
            existing = SupplierPaymentEvidence.objects.filter(
                invoice=invoice
            ).aggregate(total=Sum("amount_minor"))["total"] or 0
            if existing + amount > invoice.amount_minor:
                return fail("payment_exceeds_invoice_balance", 409)
            payment = SupplierPaymentEvidence.objects.create(
                invoice=invoice, reference=reference,
                idempotency_key=key, fingerprint=digest,
                amount_minor=amount, notes=notes, recorded_by=scope.operator,
            )
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="supplier_payment.recorded",
                entity_type="SupplierPaymentEvidence", entity_reference=str(payment.pk),
                metadata={"invoice_id": invoice.pk, "reference": reference,
                          "amount_minor": amount, "location_code": scope.location.code},
            )
    except IntegrityError:
        return fail("concurrent_payment_evidence_retry", 409)
    return JsonResponse({"payment": _row(payment), "replayed": False}, status=201)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def verify_supplier_payment(request, payment_id):
    data = parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    notes = data.get("notes")
    if not valid_text(notes, 1000):
        return fail("verification_notes_required")
    with transaction.atomic():
        payment = SupplierPaymentEvidence.objects.select_for_update().filter(
            pk=payment_id, invoice__receipt__order__location=scope.location
        ).first()
        if payment is None:
            return fail("payment_not_found", 404)
        if payment.recorded_by_id == scope.operator.pk:
            return fail("self_verification_forbidden", 403)
        if payment.status != SupplierPaymentEvidence.Status.RECORDED:
            return fail("payment_already_verified", 409)
        payment.status = SupplierPaymentEvidence.Status.VERIFIED
        payment.verified_by = scope.operator
        payment.verification_notes = notes
        payment.verified_at = timezone.now()
        payment.save(update_fields=[
            "status", "verified_by", "verification_notes", "verified_at"
        ])
        AuditEvent.objects.create(
            actor=str(request.user.pk), action="supplier_payment.verified",
            entity_type="SupplierPaymentEvidence", entity_reference=str(payment.pk),
            metadata={"invoice_id": payment.invoice_id,
                      "reference": payment.reference,
                      "location_code": scope.location.code},
        )
    return JsonResponse({"payment": _row(payment)})


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supplier_payment_reconciliation(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    invoices = SupplierInvoice.objects.filter(
        receipt__order__location=scope.location
    ).select_related("supplier").order_by("-id")[:200]
    rows = []
    for invoice in invoices:
        entries = list(invoice.payment_evidence.all())
        verified = sum(p.amount_minor for p in entries if p.status == SupplierPaymentEvidence.Status.VERIFIED)
        pending = sum(p.amount_minor for p in entries if p.status == SupplierPaymentEvidence.Status.RECORDED)
        rows.append({
            "invoice_id": invoice.pk, "invoice_number": invoice.number,
            "supplier_code": invoice.supplier.code, "status": invoice.status,
            "invoice_amount_minor": invoice.amount_minor,
            "verified_evidence_minor": verified,
            "pending_review_minor": pending,
            "uncovered_minor": max(0, invoice.amount_minor - verified - pending),
            "remaining_unverified_minor": max(0, invoice.amount_minor - verified),
            "review_status": (
                "EXCEPTION" if invoice.status != SupplierInvoice.Status.MATCHED else
                "MANUALLY_RECONCILED" if verified == invoice.amount_minor else
                "PENDING_REVIEW" if pending else
                "PARTIAL" if verified else "UNRECORDED"
            ),
        })
    return JsonResponse({
        "currency": "NGN", "limit": 200, "rows": rows,
        "note": "Verified evidence reflects manual supervisory review, not bank-confirmed settlement.",
    })
