"""Supervisor procurement: suppliers, purchase orders and idempotent partial receipts."""
import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import F, OuterRef, Subquery, BigIntegerField, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import (
    AuditEvent, GoodsReceipt, GoodsReceiptLine, InventoryItem,
    InventoryMovement, POSOperator, Product, PurchaseOrder,
    PurchaseOrderLine, Supplier,
)
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope


def fail(error, status=400):
    return JsonResponse({"error": error}, status=status)


def parse_body(request):
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def valid_text(v, maximum):
    return isinstance(v, str) and bool(v.strip()) and v == v.strip() and len(v) <= maximum


def valid_positive(v, maximum=1000000):
    return type(v) is int and 0 < v <= maximum


def scope_for(request, data):
    try:
        scope = authorize_pos_scope(
            user=request.user,
            location_code=data.get("location_code", ""),
            terminal_code=data.get("terminal_code", ""),
        )
    except (POSAccessError, TypeError, ValueError, AttributeError):
        return None
    return scope if scope.operator.role == POSOperator.Role.SUPERVISOR else None


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def order_view(order):
    lines = list(order.lines.select_related("product").order_by("id"))
    remaining = sum(line.quantity_ordered - line.quantity_received for line in lines)
    received = sum(line.quantity_received for line in lines)
    return {
        "id": order.pk, "reference": order.reference,
        "approval": "APPROVED" if hasattr(order, "approval") else "PENDING",
        "location_code": order.location.code,
        "supplier_code": order.supplier.code,
        "supplier_name": order.supplier.name,
        "status": "RECEIVED" if remaining == 0 else ("PARTIAL" if received else "OPEN"),
        "total_cost_minor": sum(l.quantity_ordered * l.unit_cost_minor for l in lines),
        "lines": [
            {
                "id": line.pk, "sku": line.product.sku, "name": line.product.name,
                "quantity_ordered": line.quantity_ordered,
                "quantity_received": line.quantity_received,
                "quantity_outstanding": line.quantity_ordered - line.quantity_received,
                "unit_cost_minor": line.unit_cost_minor,
            } for line in lines
        ],
    }


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def suppliers(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        return JsonResponse({"suppliers": list(
            Supplier.objects.filter(is_active=True).order_by("code")[:100]
            .values("id", "code", "name", "contact")
        )})
    code, name = data.get("code"), data.get("name")
    contact = data.get("contact", "")
    if not valid_text(code, 64) or not valid_text(name, 255):
        return fail("invalid_supplier")
    if not isinstance(contact, str) or len(contact) > 255:
        return fail("invalid_contact")
    try:
        with transaction.atomic():
            supplier = Supplier.objects.create(code=code, name=name, contact=contact)
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="supplier.created",
                entity_type="Supplier", entity_reference=str(supplier.pk),
                metadata={"code": code, "location_code": scope.location.code},
            )
    except IntegrityError:
        return fail("supplier_code_exists", 409)
    return JsonResponse({"supplier": {"id": supplier.pk, "code": code, "name": name}}, status=201)


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def purchase_orders(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        orders = PurchaseOrder.objects.filter(
            location=scope.location
        ).select_related("supplier", "location").order_by("-id")[:50]
        return JsonResponse({"orders": [order_view(order) for order in orders]})

    reference, supplier_code, raw_lines = (
        data.get("reference"), data.get("supplier_code"), data.get("lines")
    )
    notes = data.get("notes", "")
    if (not valid_text(reference, 64) or not valid_text(supplier_code, 64)
            or not isinstance(notes, str) or len(notes) > 2000):
        return fail("invalid_order_fields")
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= 50:
        return fail("invalid_order_lines")
    parsed = []
    seen = set()
    for line in raw_lines:
        if not isinstance(line, dict):
            return fail("invalid_order_line")
        sku = line.get("sku")
        quantity = line.get("quantity")
        cost = line.get("unit_cost_minor")
        if (not valid_text(sku, 64) or sku in seen
                or not valid_positive(quantity)
                or not valid_positive(cost, 10**12)):
            return fail("invalid_order_line")
        seen.add(sku)
        parsed.append((sku, quantity, cost))
    try:
        supplier = Supplier.objects.get(code=supplier_code, is_active=True)
    except Supplier.DoesNotExist:
        return fail("supplier_not_found", 404)
    products = {
        p.sku: p for p in Product.objects.filter(
            sku__in=seen, is_active=True, currency="NGN"
        )
    }
    if len(products) != len(parsed):
        return fail("product_not_found", 404)
    try:
        with transaction.atomic():
            order = PurchaseOrder.objects.create(
                reference=reference, supplier=supplier,
                location=scope.location, created_by=scope.operator, notes=notes,
            )
            PurchaseOrderLine.objects.bulk_create([
                PurchaseOrderLine(
                    order=order, product=products[sku],
                    quantity_ordered=qty, unit_cost_minor=cost,
                ) for sku, qty, cost in parsed
            ])
            AuditEvent.objects.create(
                actor=str(request.user.pk), action="purchase_order.created",
                entity_type="PurchaseOrder", entity_reference=str(order.pk),
                metadata={
                    "reference": reference, "supplier_code": supplier.code,
                    "location_code": scope.location.code,
                },
            )
    except IntegrityError:
        return fail("order_reference_exists", 409)
    order = PurchaseOrder.objects.select_related("supplier", "location").get(pk=order.pk)
    return JsonResponse({"order": order_view(order)}, status=201)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def purchase_order_detail(request, order_id):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    order = PurchaseOrder.objects.select_related("supplier", "location").filter(
        pk=order_id, location=scope.location
    ).first()
    return JsonResponse({"order": order_view(order)}) if order else fail("order_not_found", 404)


class ReceiptRejected(Exception):
    def __init__(self, error, status=409):
        self.error, self.status = error, status


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def receive_purchase_order(request, order_id):
    data = parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    reference, key, raw_lines = (
        data.get("reference"), data.get("idempotency_key"), data.get("lines")
    )
    if (not valid_text(reference, 128) or not valid_text(key, 128)
            or len(key) < 8 or not isinstance(raw_lines, list)
            or not 1 <= len(raw_lines) <= 50):
        return fail("invalid_receipt")
    quantities = {}
    for line in raw_lines:
        if not isinstance(line, dict):
            return fail("invalid_receipt_line")
        line_id, quantity = line.get("line_id"), line.get("quantity")
        if not valid_positive(line_id, 2**63-1) or not valid_positive(quantity):
            return fail("invalid_receipt_line")
        if line_id in quantities:
            return fail("duplicate_receipt_line")
        quantities[line_id] = quantity

    digest = fingerprint({
        "order_id": order_id, "reference": reference,
        "location_code": scope.location.code,
        "lines": sorted(quantities.items()),
    })
    try:
        with transaction.atomic():
            # Serialize all receipts on the order before checking remaining units.
            order = PurchaseOrder.objects.select_for_update().filter(
                pk=order_id, location=scope.location
            ).first()
            if order is None:
                raise ReceiptRejected("order_not_found", 404)
            previous = GoodsReceipt.objects.filter(key=key).first()
            if previous:
                if previous.order_id != order_id or previous.request_fingerprint != digest:
                    raise ReceiptRejected("idempotency_conflict")
                return JsonResponse({
                    "receipt_id": previous.pk, "replayed": True,
                    "order": order_view(order),
                })
            from .models import PurchaseOrderApproval
            if not PurchaseOrderApproval.objects.filter(order=order).exists():
                raise ReceiptRejected("purchase_order_not_approved")
            if GoodsReceipt.objects.filter(order=order, reference=reference).exists():
                raise ReceiptRejected("receipt_reference_exists")

            lines = {
                row.pk: row for row in
                PurchaseOrderLine.objects.select_for_update(of=("self",))
                .filter(order=order, pk__in=quantities).order_by("product_id")
            }
            if len(lines) != len(quantities):
                raise ReceiptRejected("order_line_not_found", 404)
            for line_id, quantity in quantities.items():
                row = lines[line_id]
                if row.quantity_received + quantity > row.quantity_ordered:
                    raise ReceiptRejected("receipt_exceeds_outstanding")

            # Lock products in a stable order to agree with supervisor stock
            # receiving, then lock/create the actual inventory rows.
            products = list(Product.objects.select_for_update().filter(
                pk__in=[line.product_id for line in lines.values()]
            ).order_by("pk"))
            if len(products) != len(lines) or any(not p.is_active for p in products):
                raise ReceiptRejected("product_unavailable")

            receipt = GoodsReceipt.objects.create(
                order=order, reference=reference, key=key,
                request_fingerprint=digest, received_by=scope.operator,
            )
            for row in sorted(lines.values(), key=lambda l: l.product_id):
                inventory, _ = InventoryItem.objects.get_or_create(
                    product_id=row.product_id, location_code=scope.location.code,
                    defaults={"quantity": 0},
                )
                inventory = InventoryItem.objects.select_for_update().get(pk=inventory.pk)
                new_quantity = inventory.quantity + quantities[row.pk]
                if new_quantity > 2**63 - 1:
                    raise ReceiptRejected("stock_overflow", 400)
                inventory.quantity = new_quantity
                inventory.save(update_fields=["quantity"])
                row.quantity_received += quantities[row.pk]
                row.save(update_fields=["quantity_received"])
                movement = InventoryMovement.objects.create(
                    inventory_item=inventory, quantity_delta=quantities[row.pk],
                    reason=InventoryMovement.Reason.PURCHASE,
                    reference=f"PO:{order.reference}/GRN:{reference}",
                )
                GoodsReceiptLine.objects.create(
                    receipt=receipt, order_line=row,
                    quantity=quantities[row.pk], movement=movement,
                )
                AuditEvent.objects.create(
                    actor=str(request.user.pk), action="purchase_order.goods_received",
                    entity_type="InventoryItem", entity_reference=str(inventory.pk),
                    metadata={
                        "purchase_order_id": order.pk, "receipt_id": receipt.pk,
                        "sku": row.product.sku, "quantity_delta": quantities[row.pk],
                        "quantity_after": new_quantity,
                        "location_code": scope.location.code,
                        "movement_id": movement.pk,
                    },
                )
            return JsonResponse({
                "receipt_id": receipt.pk, "replayed": False,
                "order": order_view(order),
            }, status=201)
    except ReceiptRejected as exc:
        return fail(exc.error, exc.status)
    except IntegrityError:
        return fail("concurrent_receipt_retry", 409)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def replenishment_report(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    raw_threshold = request.query_params.get("threshold", "5")
    if not raw_threshold.isascii() or not raw_threshold.isdecimal() or len(raw_threshold) > 6:
        return fail("invalid_threshold")
    threshold = int(raw_threshold)
    if threshold > 100000:
        return fail("invalid_threshold")
    quantities = InventoryItem.objects.filter(
        product_id=OuterRef("pk"), location_code=scope.location.code
    ).values("quantity")[:1]
    products = list(Product.objects.filter(
        is_active=True, currency="NGN"
    ).annotate(current_stock=Coalesce(
        Subquery(quantities, output_field=BigIntegerField()),
        Value(0, output_field=BigIntegerField())
    )).filter(current_stock__lte=threshold).order_by("sku")[:200])
    pending_by_product = {}
    for line in PurchaseOrderLine.objects.filter(
        order__location=scope.location,
        order__approval__isnull=False,
        product_id__in=[p.pk for p in products],
        quantity_received__lt=F("quantity_ordered"),
    ).select_related("order", "order__supplier"):
        remaining = line.quantity_ordered - line.quantity_received
        pending_by_product[line.product_id] = pending_by_product.get(line.product_id, 0) + remaining
    return JsonResponse({
        "location_code": scope.location.code,
        "threshold": threshold, "limit": 200,
        "products": [{
            "sku": product.sku, "name": product.name,
            "current_stock": product.current_stock,
            "outstanding_order_units": pending_by_product.get(product.pk, 0),
            "reorder_gap_units": max(0, threshold + 1 - product.current_stock - pending_by_product.get(product.pk, 0)),
        } for product in products],
    })
