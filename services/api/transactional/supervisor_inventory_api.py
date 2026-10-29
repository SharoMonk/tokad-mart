"""Supervisor-authorized, atomic stock receipts and adjustments."""
import hashlib
import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import (
    AuditEvent, InventoryItem, InventoryMovement, POSOperator,
    Product, StockOperation,
)
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope


def _error(code, status=400):
    return JsonResponse({"error": code}, status=status)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def supervisor_stock_operation(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return _error("invalid_body")
    except (ValueError, UnicodeDecodeError, TypeError):
        return _error("invalid_body")

    try:
        scope = authorize_pos_scope(
            user=request.user,
            location_code=data.get("location_code", ""),
            terminal_code=data.get("terminal_code", ""),
        )
    except (POSAccessError, TypeError, ValueError):
        return _error("pos_access_denied", 403)
    if scope.operator.role != POSOperator.Role.SUPERVISOR:
        return _error("supervisor_required", 403)

    sku, operation, quantity = data.get("sku"), data.get("operation"), data.get("quantity")
    reference, notes, key = data.get("reference"), data.get("notes"), data.get("idempotency_key")
    if not isinstance(sku, str) or not sku or len(sku) > 64:
        return _error("invalid_sku")
    if operation not in ("RECEIVE", "ADJUST"):
        return _error("invalid_operation")
    if type(quantity) is not int or quantity == 0 or abs(quantity) > 1000000:
        return _error("invalid_quantity")
    if operation == "RECEIVE" and quantity < 0:
        return _error("receipt_must_increase_stock")
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 255:
        return _error("reference_required")
    if not isinstance(notes, str) or not notes.strip() or len(notes) > 2000:
        return _error("notes_required")
    if not isinstance(key, str) or not 8 <= len(key) <= 128 or not key.isascii() or not key.isprintable():
        return _error("invalid_idempotency_key")
    # The same key with changed request semantics is a conflict, not a second write.
    canonical = {
        "sku": sku, "operation": operation, "quantity": quantity,
        "reference": reference.strip(), "notes": notes.strip(),
        "location_code": scope.location.code,
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    try:
        with transaction.atomic():
            previous = StockOperation.objects.select_related(
                "movement__inventory_item"
            ).filter(key=key).first()
            if previous:
                if previous.request_fingerprint != fingerprint:
                    return _error("idempotency_conflict", 409)
                return JsonResponse({
                    "movement_id": previous.movement_id,
                    "quantity_after": previous.quantity_after,
                    "replayed": True,
                })

            # Lock the product first: serializes creation of a previously absent
            # InventoryItem. Normal sales lock the InventoryItem row itself.
            product = Product.objects.select_for_update().filter(sku=sku).first()
            if product is None or not product.is_active:
                return _error("product_not_found", 404)
            inventory, _ = InventoryItem.objects.get_or_create(
                product=product, location_code=scope.location.code,
                defaults={"quantity": 0},
            )
            inventory = InventoryItem.objects.select_for_update().get(pk=inventory.pk)
            new_quantity = inventory.quantity + quantity
            if new_quantity < 0:
                return _error("insufficient_stock", 409)
            if new_quantity > 2**63 - 1:
                return _error("stock_overflow", 400)
            inventory.quantity = new_quantity
            inventory.save(update_fields=["quantity"])
            movement = InventoryMovement.objects.create(
                inventory_item=inventory, quantity_delta=quantity,
                reason=(InventoryMovement.Reason.PURCHASE if operation == "RECEIVE"
                        else InventoryMovement.Reason.ADJUSTMENT),
                reference=reference.strip(),
            )
            StockOperation.objects.create(
                key=key, request_fingerprint=fingerprint, actor=request.user,
                movement=movement, quantity_after=new_quantity,
            )
            AuditEvent.objects.create(
                actor=str(request.user.pk),
                action=("inventory.received" if operation == "RECEIVE"
                        else "inventory.adjusted"),
                entity_type="InventoryItem", entity_reference=str(inventory.pk),
                metadata={
                    "sku": sku, "quantity_delta": quantity,
                    "quantity_after": new_quantity, "operation": operation,
                    "reference": reference.strip(), "notes": notes.strip(),
                    "location_code": scope.location.code,
                    "movement_id": movement.pk,
                },
            )
            return JsonResponse({
                "movement_id": movement.pk, "quantity_after": new_quantity,
                "replayed": False,
            }, status=201)
    except IntegrityError:
        # Concurrent replay; do not partially commit stock increments.
        return _error("concurrent_stock_operation_retry", 409)
