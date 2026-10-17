from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse

from .models import InventoryItem, POSOperator, Product, Sale
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope


@api_view(["GET"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def pos_scope(request):
    operator = POSOperator.objects.get(user=request.user, is_active=True)
    locations = []
    for location in operator.locations.filter(is_active=True).order_by("code"):
        terminals = list(
            operator.terminals.filter(location=location, is_active=True)
            .values("code", "name")
            .order_by("code")
        )
        if terminals:
            locations.append({"code": location.code, "name": location.name, "terminals": terminals})
    return JsonResponse({"locations": locations})


@api_view(["GET"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def pos_catalog(request):
    location_code = request.query_params.get("location_code", "")
    terminal_code = request.query_params.get("terminal_code", "")
    try:
        authorize_pos_scope(user=request.user, location_code=location_code, terminal_code=terminal_code)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)

    query = request.query_params.get("q", "").strip()
    if not query:
        return JsonResponse({"products": []})
    products = Product.objects.filter(is_active=True, currency="NGN")
    from django.db.models import Q
    products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query)).order_by("name")[:30]
    stock = {
        item.product_id: item.quantity
        for item in InventoryItem.objects.filter(location_code=location_code, product__in=products)
    }
    return JsonResponse({"products": [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "currency": product.currency,
            "unit_price_minor": product.unit_price_minor,
            "stock": stock.get(product.id, 0),
        }
        for product in products
    ]})


@api_view(["GET"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def pos_receipt(request, sale_id):
    location_code = request.query_params.get("location_code", "")
    terminal_code = request.query_params.get("terminal_code", "")
    try:
        authorize_pos_scope(user=request.user, location_code=location_code, terminal_code=terminal_code)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)
    sale = Sale.objects.filter(id=sale_id, location_code=location_code).first()
    if sale is None:
        return JsonResponse({"error": "sale_not_found"}, status=404)
    if sale.status != Sale.Status.COMPLETED:
        return JsonResponse({"error": "sale_not_completed"}, status=409)
    return JsonResponse({
        "sale_id": sale.id,
        "reference": str(sale.reference),
        "created_at": sale.created_at.isoformat(),
        "currency": sale.currency,
        "total_minor": sale.total_minor,
        "lines": [{
            "name": line.name_snapshot,
            "sku": line.sku_snapshot,
            "quantity": line.quantity,
            "unit_price_minor": line.unit_price_minor,
            "line_total_minor": line.line_total_minor,
        } for line in sale.lines.all().order_by("id")],
        "payments": [{
            "method": payment.method,
            "amount_minor": payment.amount_minor,
            "status": payment.status,
        } for payment in sale.payments.all().order_by("id")],
    })
