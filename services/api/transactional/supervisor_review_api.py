"""Supervisor-only review of closed cashier drawers.

Reviews never modify the shift's counted or expected cash and cannot be repeated.
"""
import json

from django.db import transaction
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import AuditEvent, CashierShift, POSOperator, ShiftReconciliationReview
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supervisor_reconciliation(request, shift_id):
    operator = POSOperator.objects.get(user=request.user, is_active=True)
    if operator.role != POSOperator.Role.SUPERVISOR:
        return JsonResponse({"error": "supervisor_required"}, status=403)
    try:
        shift = CashierShift.objects.select_related("location", "terminal").get(pk=shift_id)
        authorize_pos_scope(
            user=request.user, location_code=shift.location.code,
            terminal_code=shift.terminal.code,
        )
    except CashierShift.DoesNotExist:
        return JsonResponse({"error": "shift_not_found"}, status=404)
    except POSAccessError:
        return JsonResponse({"error": "pos_access_denied"}, status=403)

    if request.method == "GET":
        review = ShiftReconciliationReview.objects.filter(shift=shift).first()
        return JsonResponse({
            "shift_id": shift.pk,
            "shift_status": shift.status,
            "expected_cash_minor": shift.expected_cash_minor,
            "closing_cash_minor": shift.closing_cash_minor,
            "variance_minor": (
                shift.closing_cash_minor - shift.expected_cash_minor
                if shift.status == CashierShift.Status.CLOSED else None
            ),
            "review": (
                {"decision": review.decision, "notes": review.notes,
                 "supervisor_id": review.supervisor_id,
                 "reviewed_at": review.reviewed_at.isoformat()} if review else None
            ),
        })

    try:
        data = json.loads(request.body)
        decision = data.get("decision")
        notes = data.get("notes")
        if decision not in ShiftReconciliationReview.Decision.values:
            raise ValueError("decision must be APPROVED or REJECTED")
        if not isinstance(notes, str) or not notes.strip() or len(notes) > 2000:
            raise ValueError("nonempty notes of at most 2000 characters are required")
    except (UnicodeDecodeError, ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "invalid_review_request"}, status=400)

    with transaction.atomic():
        shift = CashierShift.objects.select_for_update().get(pk=shift.pk)
        if shift.status != CashierShift.Status.CLOSED:
            return JsonResponse({"error": "shift_not_closed"}, status=409)
        if ShiftReconciliationReview.objects.filter(shift=shift).exists():
            return JsonResponse({"error": "already_reviewed"}, status=409)
        review = ShiftReconciliationReview.objects.create(
            shift=shift, supervisor=operator, decision=decision, notes=notes.strip(),
        )
        AuditEvent.objects.create(
            actor=str(request.user.pk),
            action="shift.reconciliation_reviewed",
            entity_type="CashierShift", entity_reference=str(shift.pk),
            metadata={
                "review_id": review.pk, "decision": decision,
                "variance_minor": shift.closing_cash_minor - shift.expected_cash_minor,
            },
        )
    return JsonResponse({
        "review_id": review.pk,
        "shift_id": shift.pk,
        "decision": review.decision,
        "variance_minor": shift.closing_cash_minor - shift.expected_cash_minor,
    }, status=201)
