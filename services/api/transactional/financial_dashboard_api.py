"""Scoped management dashboard and independently reviewed operating expenses."""
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import (
    AuditEvent, CashierShift, ExpenseReview, Payment, Sale,
    ShiftReconciliationReview, StoreExpense, SupplierInvoice,
    SupplierPaymentEvidence,
)
from .permissions import IsPOSOperator
from .supervisor_procurement_api import fail, parse_body, scope_for, valid_text


def _date_range(data):
    try:
        start = date.fromisoformat(data.get("start", ""))
        end = date.fromisoformat(data.get("end", ""))
        if start > end or (end - start).days > 31:
            return None
        return start, end
    except (TypeError, ValueError, AttributeError):
        return None


def _expense(expense):
    review = ExpenseReview.objects.filter(expense=expense).first()
    return {
        "id": expense.pk, "reference": expense.reference,
        "category": expense.category, "description": expense.description,
        "amount_minor": expense.amount_minor, "incurred_on": expense.incurred_on.isoformat(),
        "review_status": review.decision if review else "PENDING",
    }


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def expenses(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        rows = StoreExpense.objects.filter(location=scope.location).order_by("-id")[:100]
        return JsonResponse({"expenses": [_expense(row) for row in rows], "limit": 100})

    reference, category, description, amount, day = (
        data.get("reference"), data.get("category"), data.get("description"),
        data.get("amount_minor"), data.get("incurred_on"),
    )
    if (not valid_text(reference, 128) or not valid_text(category, 64)
            or not valid_text(description, 500)
            or type(amount) is not int or amount <= 0 or amount > 10**12):
        return fail("invalid_expense")
    try:
        incurred_on = date.fromisoformat(day)
        if incurred_on > date.today():
            return fail("future_expense_date")
    except (TypeError, ValueError):
        return fail("invalid_expense_date")
    try:
        with transaction.atomic():
            expense = StoreExpense.objects.create(
                location=scope.location, reference=reference, category=category,
                description=description, amount_minor=amount, incurred_on=incurred_on,
                recorded_by=scope.operator,
            )
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="expense.recorded",
                entity_type="StoreExpense", entity_reference=str(expense.pk),
                metadata={"location_code": scope.location.code, "reference": reference,
                          "amount_minor": amount},
            )
    except IntegrityError:
        return fail("expense_reference_exists", 409)
    return JsonResponse({"expense": _expense(expense)}, status=201)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def expense_review(request, expense_id):
    data = parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    notes, decision = data.get("notes"), data.get("decision")
    if not valid_text(notes, 1000) or decision not in ("APPROVED", "REJECTED"):
        return fail("invalid_review")
    with transaction.atomic():
        expense = StoreExpense.objects.select_for_update().filter(
            pk=expense_id, location=scope.location
        ).first()
        if expense is None:
            return fail("expense_not_found", 404)
        if expense.recorded_by_id == scope.operator.pk:
            return fail("self_review_forbidden", 403)
        if ExpenseReview.objects.filter(expense=expense).exists():
            return fail("already_reviewed", 409)
        ExpenseReview.objects.create(
            expense=expense, reviewed_by=scope.operator,
            decision=decision, notes=notes,
        )
        AuditEvent.objects.create(
            actor=str(request.user.pk), action="expense.reviewed",
            entity_type="StoreExpense", entity_reference=str(expense.pk),
            metadata={"decision": decision, "location_code": scope.location.code},
        )
    return JsonResponse({"expense_id": expense_id, "decision": decision})


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def financial_dashboard(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    dates = _date_range(request.query_params)
    if dates is None:
        return fail("invalid_date_range")
    start, end = dates
    sales = Sale.objects.filter(
        location_code=scope.location.code, status=Sale.Status.COMPLETED,
        completed_at__date__gte=start, completed_at__date__lte=end,
        currency="NGN",
    )
    by_day = list(sales.annotate(day=TruncDate("completed_at")).values("day")
                  .annotate(total_minor=Sum("total_minor")).order_by("day"))
    sales_total = sales.aggregate(total=Sum("total_minor"))["total"] or 0

    shifts = CashierShift.objects.filter(
        location=scope.location, status=CashierShift.Status.CLOSED,
        closed_at__date__gte=start, closed_at__date__lte=end,
    ).order_by("-closed_at")[:100]
    variance_rows = []
    for shift in shifts:
        expected = shift.expected_cash_minor
        counted = shift.closing_cash_minor
        variance = counted - expected if expected is not None and counted is not None else None
        review = ShiftReconciliationReview.objects.filter(shift=shift).first()
        variance_rows.append({
            "shift_id": shift.pk, "terminal": shift.terminal.code,
            "variance_minor": variance,
            "review_status": review.decision if review else "PENDING",
        })
    reviewed_expenses = StoreExpense.objects.filter(
        location=scope.location, incurred_on__gte=start, incurred_on__lte=end,
        review__decision="APPROVED",
    )
    approved_expenses_minor = reviewed_expenses.aggregate(
        total=Sum("amount_minor")
    )["total"] or 0
    pending_expenses_minor = StoreExpense.objects.filter(
        location=scope.location, incurred_on__gte=start, incurred_on__lte=end,
        review__isnull=True,
    ).aggregate(total=Sum("amount_minor"))["total"] or 0

    invoices = SupplierInvoice.objects.filter(
        receipt__order__location=scope.location,
        recorded_at__date__gte=start, recorded_at__date__lte=end,
    ).prefetch_related("payment_evidence")
    supplier_rows = []
    for invoice in invoices:
        evidence = list(invoice.payment_evidence.all())
        supplier_rows.append({
            "invoice_id": invoice.pk, "invoice_number": invoice.number,
            "status": invoice.status, "amount_minor": invoice.amount_minor,
            "verified_evidence_minor": sum(
                p.amount_minor for p in evidence
                if p.status == SupplierPaymentEvidence.Status.VERIFIED
            ),
            "pending_review_minor": sum(
                p.amount_minor for p in evidence
                if p.status == SupplierPaymentEvidence.Status.RECORDED
            ),
        })
    return JsonResponse({
        "location_code": scope.location.code,
        "start": start.isoformat(), "end": end.isoformat(), "currency": "NGN",
        "sales": {
            "completed_sale_count": sales.count(), "gross_minor": sales_total,
            "daily": [{"date": row["day"].isoformat(), "gross_minor": row["total_minor"]}
                      for row in by_day],
        },
        "cashier_shifts": variance_rows,
        "expenses": {
            "approved_minor": approved_expenses_minor,
            "pending_review_minor": pending_expenses_minor,
        },
        "supplier_invoice_exposure": supplier_rows,
        "disclaimer": "Gross sales is not cash collected, net profit, or bank balance. Expenses are entered costs, not verified disbursements; supplier evidence is manual.",
        "limits": {"shift_rows": 100, "supplier_invoice_rows": None},
    })
