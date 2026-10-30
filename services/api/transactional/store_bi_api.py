"""Scoped business intelligence: sales trends, fast movers and inventory alerts."""
from django.db.models import Sum, Count, OuterRef, Subquery, Value, BigIntegerField
from django.db.models.functions import Coalesce, TruncDate
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import InventoryItem, Product, Sale, SaleLine
from .permissions import IsPOSOperator
from .financial_dashboard_api import _date_range
from .supervisor_procurement_api import fail, scope_for


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def store_bi_insights(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    dates = _date_range(request.query_params)
    if dates is None:
        return fail("invalid_date_range")
    start, end = dates
    threshold = request.query_params.get("threshold", "5")
    if not threshold.isascii() or not threshold.isdecimal() or len(threshold) > 6 or int(threshold) > 100000:
        return fail("invalid_threshold")
    threshold = int(threshold)
    completed = Sale.objects.filter(
        location_code=scope.location.code, status=Sale.Status.COMPLETED,
        currency="NGN", completed_at__date__range=(start, end)
    )
    daily = list(completed.annotate(day=TruncDate("completed_at"))
                 .values("day").annotate(
                     sales=Count("id"), gross_minor=Sum("total_minor")
                 ).order_by("day"))
    top_products = list(SaleLine.objects.filter(
        sale__in=completed
    ).values("sku_snapshot", "name_snapshot").annotate(
        units=Sum("quantity"), revenue_minor=Sum("line_total_minor")
    ).order_by("-units", "sku_snapshot")[:20])
    quantities = InventoryItem.objects.filter(
        product_id=OuterRef("pk"), location_code=scope.location.code
    ).values("quantity")[:1]
    low = list(Product.objects.filter(is_active=True, currency="NGN").annotate(
        stock=Coalesce(Subquery(quantities, output_field=BigIntegerField()),
                       Value(0, output_field=BigIntegerField()))
    ).filter(stock__lte=threshold).order_by("sku").values(
        "sku", "name", "stock"
    )[:50])
    return JsonResponse({
        "location_code": scope.location.code,
        "start": start.isoformat(), "end": end.isoformat(),
        "currency": "NGN", "threshold": threshold,
        "daily_sales": [{"date": row["day"].isoformat(),
                         "count": row["sales"], "gross_minor": row["gross_minor"]}
                        for row in daily],
        "top_products": top_products,
        "low_stock": low,
        "limits": {"top_products": 20, "low_stock": 50},
        "note": "Revenue is recorded sale-line gross, not profit; inventory is current stock, not a historical snapshot.",
    })
