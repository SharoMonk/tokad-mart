"""Supervisor-only canonical product registration and barcode mapping."""
import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import AuditEvent, POSOperator, Product, ProductBarcode
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope


def _error(code, status=400):
    return JsonResponse({"error": code}, status=status)


def _body(request):
    try:
        value = json.loads(request.body)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _supervisor(request, data):
    try:
        scope = authorize_pos_scope(
            user=request.user,
            location_code=data.get("location_code", ""),
            terminal_code=data.get("terminal_code", ""),
        )
    except (POSAccessError, TypeError, ValueError):
        return None
    return scope if scope.operator.role == POSOperator.Role.SUPERVISOR else None


def _text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit and value == value.strip()


def _valid_code(value):
    return _text(value, 64) and all(33 <= ord(char) <= 126 for char in value)


def _serialize(product):
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "currency": product.currency,
        "unit_price_minor": product.unit_price_minor,
        "is_active": product.is_active,
        "barcodes": list(product.barcodes.order_by("code").values_list("code", flat=True)),
    }


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supervisor_product_create(request):
    data = dict(request.query_params.items()) if request.method == "GET" else _body(request)
    if data is None:
        return _error("invalid_request")
    scope = _supervisor(request, data)
    if scope is None:
        return _error("supervisor_scope_required", 403)
    sku = data.get("sku")
    if request.method == "GET":
        if not _valid_code(sku):
            return _error("invalid_sku")
        product = Product.objects.filter(sku=sku).first()
        return JsonResponse({"product": _serialize(product)}) if product else _error("product_not_found", 404)
    name = data.get("name")
    price = data.get("unit_price_minor")
    if not _valid_code(sku) or not _text(name, 255):
        return _error("invalid_product_fields")
    if type(price) is not int or price <= 0 or price > 10**12:
        return _error("invalid_price_minor")
    # Cash POS currently supports NGN only. No client-controlled currency or stock.
    if data.get("currency", "NGN") != "NGN":
        return _error("unsupported_currency")
    if ProductBarcode.objects.filter(code=sku).exists():
        return _error("sku_conflicts_with_barcode", 409)
    try:
        with transaction.atomic():
            product = Product.objects.create(
                sku=sku, name=name, currency="NGN", unit_price_minor=price
            )
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="product.created",
                entity_type="Product", entity_reference=str(product.pk),
                metadata={"sku": sku, "unit_price_minor": price,
                          "location_code": scope.location.code},
            )
    except IntegrityError:
        return _error("sku_already_exists", 409)
    return JsonResponse({"product": _serialize(product)}, status=201)


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supervisor_product_barcodes(request, product_id):
    data = (
        dict(request.query_params.items()) if request.method == "GET"
        else _body(request)
    )
    if data is None:
        return _error("invalid_request")
    scope = _supervisor(request, data)
    if scope is None:
        return _error("supervisor_scope_required", 403)
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return _error("product_not_found", 404)
    if request.method == "GET":
        return JsonResponse({"product": _serialize(product)})
    code = data.get("code")
    if not _valid_code(code):
        return _error("invalid_barcode")
    if Product.objects.filter(sku=code).exclude(pk=product_id).exists():
        return _error("barcode_conflicts_with_sku", 409)
    try:
        with transaction.atomic():
            mapping, created = ProductBarcode.objects.get_or_create(
                code=code, defaults={"product": product}
            )
            if mapping.product_id != product.pk:
                return _error("barcode_assigned_to_another_product", 409)
            if created:
                AuditEvent.objects.create(
                    actor=str(request.user.pk), action="product.barcode_added",
                    entity_type="Product", entity_reference=str(product.pk),
                    metadata={"code": code, "location_code": scope.location.code},
                )
    except IntegrityError:
        return _error("barcode_conflict_retry", 409)
    return JsonResponse({"product": _serialize(product)}, status=201 if created else 200)
