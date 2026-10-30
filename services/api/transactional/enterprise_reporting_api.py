"""Multi-location operational reports and spreadsheet-safe CSV downloads.

Only assigned active locations are aggregated. No unauthorised scope fallback.
"""
import csv
from datetime import date
from io import StringIO

from django.db.models import Sum, Count, OuterRef, Subquery, BigIntegerField, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import (
    CashierShift, InventoryItem, POSLocation, POSOperator, Product,
    Sale, ShiftReconciliationReview, StoreExpense, SupplierInvoice,
    SupplierPaymentEvidence,
)
from .permissions import IsPOSOperator
from .supervisor_procurement_api import fail
from .financial_dashboard_api import _date_range


def _authorized(request):
    user = request.user
    if not user.is_authenticated or not user.is_staff:
        return None
    operator = POSOperator.objects.filter(
        user=user, is_active=True, role=POSOperator.Role.SUPERVISOR
    ).first()
    return operator


def _locations(request):
    operator = _authorized(request)
    if operator is None:
        return None
    accessible = POSLocation.objects.filter(
        is_active=True, operator_assignments__operator=operator
    ).distinct().order_by("code")
    requested = request.query_params.get("location_code", "")
    if requested:
        # Never allow an arbitrary location code to expand authorized access.
        accessible = accessible.filter(code=requested)
    return list(accessible)


def _query(request):
    dates = _date_range(request.query_params)
    if dates is None:
        return None
    locations = _locations(request)
    if locations is None:
        return None
    if request.query_params.get("location_code") and not locations:
        return None
    return dates, locations


def _totals(location, start, end):
    sales = Sale.objects.filter(
        location_code=location.code,
        status=Sale.Status.COMPLETED, currency="NGN",
        completed_at__date__range=(start, end),
    )
    sale_aggregate = sales.aggregate(gross=Sum("total_minor"), count=Count("id"))
    closed = CashierShift.objects.filter(
        location=location, status=CashierShift.Status.CLOSED,
        closed_at__date__range=(start, end),
    )
    counted = list(closed.values("id", "closing_cash_minor", "expected_cash_minor"))
    variance = sum(
        entry["closing_cash_minor"] - entry["expected_cash_minor"]
        for entry in counted
        if entry["closing_cash_minor"] is not None
        and entry["expected_cash_minor"] is not None
    )
    expenses = StoreExpense.objects.filter(
        location=location, incurred_on__range=(start, end),
        review__decision="APPROVED",
    ).aggregate(amount=Sum("amount_minor"))["amount"] or 0
    return {
        "location_code": location.code, "name": location.name,
        "completed_sales": sale_aggregate["count"] or 0,
        "gross_sales_minor": sale_aggregate["gross"] or 0,
        "closed_shifts": len(counted),
        "cashier_variance_minor": variance,
        "approved_expenses_minor": expenses,
    }


def _csv_cell(value):
    """Prevent spreadsheet formula injection on exported identifiers and labels."""
    string = str(value if value is not None else "")
    if string.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + string
    return string


def _csv_response(name, headers, rows):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(value) for value in row])
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def enterprise_summary(request):
    query = _query(request)
    if query is None:
        return fail("invalid_or_unauthorized_reporting_scope", 403)
    (start, end), locations = query
    rows = [_totals(location, start, end) for location in locations]
    return JsonResponse({
        "start": start.isoformat(), "end": end.isoformat(),
        "currency": "NGN", "locations": rows,
        "totals": {
            "completed_sales": sum(x["completed_sales"] for x in rows),
            "gross_sales_minor": sum(x["gross_sales_minor"] for x in rows),
            "cashier_variance_minor": sum(x["cashier_variance_minor"] for x in rows),
            "approved_expenses_minor": sum(x["approved_expenses_minor"] for x in rows),
        },
        "note": "Gross sales and reviewed expense totals are operational figures, not profit or bank balances.",
    })


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def enterprise_csv(request):
    query = _query(request)
    if query is None:
        return fail("invalid_or_unauthorized_reporting_scope", 403)
    (start, end), locations = query
    report_type = request.query_params.get("report_type", "daily")
    if report_type not in ("daily", "stock", "closing"):
        return fail("invalid_report_type")
    if report_type == "daily":
        rows = [_totals(location, start, end) for location in locations]
        return _csv_response(
            f"tokad-daily-{start}-{end}.csv",
            ["location_code", "location_name", "sales_count", "gross_sales_minor",
             "closed_shift_count", "cashier_variance_minor", "approved_expenses_minor"],
            ((r["location_code"], r["name"], r["completed_sales"],
              r["gross_sales_minor"], r["closed_shifts"], r["cashier_variance_minor"],
              r["approved_expenses_minor"]) for r in rows),
        )
    if report_type == "closing":
        scope_ids = [location.pk for location in locations]
        shifts = CashierShift.objects.filter(
            location_id__in=scope_ids,
            status=CashierShift.Status.CLOSED,
            closed_at__date__range=(start, end),
        ).select_related("location", "terminal", "operator__user").order_by("id")
        return _csv_response(
            f"tokad-closing-{start}-{end}.csv",
            ["location_code", "shift_id", "closed_at", "terminal_code",
             "cashier_id", "expected_cash_minor", "counted_cash_minor",
             "variance_minor", "review_status"],
            (
                (shift.location.code, shift.pk, shift.closed_at.isoformat(),
                 shift.terminal.code, shift.operator.user_id,
                 shift.expected_cash_minor, shift.closing_cash_minor,
                 shift.closing_cash_minor - shift.expected_cash_minor
                 if shift.closing_cash_minor is not None
                 and shift.expected_cash_minor is not None else "",
                 ("APPROVED" if ShiftReconciliationReview.objects.filter(
                     shift=shift, decision="APPROVED"
                 ).exists() else "REJECTED" if ShiftReconciliationReview.objects.filter(
                     shift=shift, decision="REJECTED"
                 ).exists() else "PENDING"))
                for shift in shifts
            ),
        )
    quantities = InventoryItem.objects.filter(
        product_id=OuterRef("pk"), location_code=OuterRef("location_code")
    ).values("quantity")[:1]
    # Report current balances, with zero-stock rows for active products.
    product_rows = Product.objects.filter(
        is_active=True, currency="NGN"
    ).order_by("sku").values("sku", "name", "unit_price_minor")
    def stock_rows():
        for location in locations:
            present = dict(InventoryItem.objects.filter(
                location_code=location.code
            ).values_list("product_id", "quantity"))
            for product in Product.objects.filter(
                is_active=True, currency="NGN"
            ).order_by("sku").values("id", "sku", "name", "unit_price_minor").iterator():
                yield (
                    location.code, product["sku"], product["name"],
                    present.get(product["id"], 0), product["unit_price_minor"],
                )
    return _csv_response(
        f"tokad-stock-{end}.csv",
        ["location_code", "sku", "product_name", "stock_units", "selling_price_minor"],
        stock_rows(),
    )
