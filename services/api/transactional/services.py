from dataclasses import dataclass
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from .models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
    Product,
    Sale,
    SaleLine,
)


class CheckoutError(Exception):
    """Raised when a checkout cannot be completed without violating a domain invariant."""


@dataclass(frozen=True)
class CheckoutLine:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class CheckoutResult:
    sale_id: int
    reference: UUID
    total_minor: int


def _fingerprint(lines: list[CheckoutLine], location_code: str, currency: str) -> str:
    import hashlib

    canonical = "|".join(f"{line.product_id}:{line.quantity}" for line in lines)
    raw = f"{location_code}|{currency}|{canonical}".encode()
    return hashlib.sha256(raw).hexdigest()


def _result_from_record(record: IdempotencyRecord) -> CheckoutResult:
    payload = record.response_payload
    return CheckoutResult(
        sale_id=int(payload["sale_id"]),
        reference=UUID(str(payload["reference"])),
        total_minor=int(payload["total_minor"]),
    )


@transaction.atomic
def checkout_sale(
    *,
    lines: list[CheckoutLine],
    location_code: str,
    currency: str,
    idempotency_key: str,
) -> CheckoutResult:
    if not lines:
        raise CheckoutError("checkout requires at least one line")
    if any(line.quantity <= 0 for line in lines):
        raise CheckoutError("line quantity must be positive")

    fingerprint = _fingerprint(lines, location_code, currency)
    existing = IdempotencyRecord.objects.filter(key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise CheckoutError("idempotency key was reused with a different request")
        return _result_from_record(existing)

    product_ids = sorted({line.product_id for line in lines})
    products = {
        p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)
    }
    if len(products) != len(product_ids):
        raise CheckoutError("one or more products are unavailable")

    inventory = {
        item.product_id: item
        for item in (
            InventoryItem.objects.select_for_update()
            .filter(
                product_id__in=product_ids,
                location_code=location_code,
            )
            .order_by("product_id")
        )
    }
    if len(inventory) != len(product_ids):
        raise CheckoutError("inventory record is missing")

    total = 0
    resolved: list[tuple[Product, int, int]] = []
    for line in lines:
        product = products[line.product_id]
        item = inventory[line.product_id]
        if item.quantity < line.quantity:
            raise CheckoutError(f"insufficient stock for {product.sku}")
        line_total = product.unit_price_minor * line.quantity
        total += line_total
        resolved.append((product, line.quantity, line_total))

    sale = Sale.objects.create(
        reference=uuid4(),
        location_code=location_code,
        currency=currency,
        subtotal_minor=total,
        total_minor=total,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.now(),
    )

    for product, quantity, line_total in resolved:
        SaleLine.objects.create(
            sale=sale,
            product=product,
            sku_snapshot=product.sku,
            name_snapshot=product.name,
            quantity=quantity,
            unit_price_minor=product.unit_price_minor,
            line_total_minor=line_total,
        )
        item = inventory[product.id]
        item.quantity -= quantity
        item.save(update_fields=["quantity"])
        InventoryMovement.objects.create(
            inventory_item=item,
            quantity_delta=-quantity,
            reason=InventoryMovement.Reason.SALE,
            reference=str(sale.reference),
        )

    AuditEvent.objects.create(
        actor="system",
        action="sale.completed",
        entity_type="Sale",
        entity_reference=str(sale.reference),
        metadata={"total_minor": total, "currency": currency},
    )

    result = CheckoutResult(sale.id, sale.reference, total)
    IdempotencyRecord.objects.create(
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_payload={
            "sale_id": result.sale_id,
            "reference": str(result.reference),
            "total_minor": result.total_minor,
        },
    )
    return result
