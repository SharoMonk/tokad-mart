from dataclasses import dataclass
from uuid import UUID, uuid4

from django.db import connection, transaction
from django.utils import timezone

from .exceptions import (
    CheckoutError,
    InsufficientStockError,
    InventoryMissingError,
    ProductUnavailableError,
)
from .models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
    Product,
    Sale,
    SaleLine,
)


@dataclass(frozen=True)
class CheckoutLine:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class CheckoutResult:
    sale_id: int
    reference: UUID
    total_minor: int


def _fingerprint(
    lines: list[CheckoutLine],
    location_code: str,
    currency: str,
) -> str:
    import hashlib

    canonical_lines = sorted((line.product_id, line.quantity) for line in lines)

    canonical = "|".join(
        f"{product_id}:{quantity}" for product_id, quantity in canonical_lines
    )

    raw = f"{location_code}|{currency}|{canonical}".encode()

    return hashlib.sha256(raw).hexdigest()


def _result_from_record(
    record: IdempotencyRecord,
) -> CheckoutResult:
    payload = record.response_payload

    if not payload:
        raise CheckoutError("idempotency key is currently being processed")

    return CheckoutResult(
        sale_id=int(payload["sale_id"]),
        reference=UUID(str(payload["reference"])),
        total_minor=int(payload["total_minor"]),
    )


def _validate_idempotency_record(
    record: IdempotencyRecord,
    fingerprint: str,
) -> None:
    """Ensure an existing idempotency key belongs to the same request."""

    if record.request_fingerprint != fingerprint:
        raise CheckoutError("idempotency key was reused with a different request")


def _lock_idempotency_key(key: str) -> None:
    """
    Serialize transactions using the same idempotency key.

    pg_advisory_xact_lock() is transaction-scoped, so PostgreSQL
    automatically releases the lock when the surrounding transaction
    commits or rolls back.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [key],
        )


def _claim_idempotency_key(
    *,
    key: str,
    fingerprint: str,
) -> IdempotencyRecord | None:
    """
    Claim an idempotency key.

    The caller must already hold the transaction-scoped advisory lock
    for this key.
    """
    existing = IdempotencyRecord.objects.filter(key=key).first()

    if existing is not None:
        _validate_idempotency_record(
            existing,
            fingerprint,
        )
        return existing

    IdempotencyRecord.objects.create(
        key=key,
        request_fingerprint=fingerprint,
        response_payload={},
    )

    return None


@transaction.atomic
def checkout_sale(
    *,
    lines: list[CheckoutLine],
    location_code: str,
    currency: str,
    idempotency_key: str,
) -> CheckoutResult:
    """Complete a sale atomically."""
    if not lines:
        raise CheckoutError("checkout requires at least one line")

    if any(line.quantity <= 0 for line in lines):
        raise CheckoutError("line quantity must be positive")

    fingerprint = _fingerprint(
        lines,
        location_code,
        currency,
    )

    _lock_idempotency_key(idempotency_key)

    existing = _claim_idempotency_key(
        key=idempotency_key,
        fingerprint=fingerprint,
    )

    if existing is not None:
        return _result_from_record(existing)

    product_ids = sorted({line.product_id for line in lines})

    products = {
        product.id: product
        for product in Product.objects.filter(
            id__in=product_ids,
            is_active=True,
        )
    }

    if len(products) != len(product_ids):
        raise ProductUnavailableError("one or more products are unavailable")

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
        raise InventoryMissingError("inventory record is missing")

    total = 0
    resolved: list[tuple[Product, int, int]] = []

    for line in lines:
        product = products[line.product_id]
        item = inventory[line.product_id]

        if item.quantity < line.quantity:
            raise InsufficientStockError(
                f"insufficient stock for {product.sku}"
            )

        line_total = product.unit_price_minor * line.quantity

        total += line_total

        resolved.append(
            (
                product,
                line.quantity,
                line_total,
            )
        )

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
        metadata={
            "total_minor": total,
            "currency": currency,
        },
    )

    result = CheckoutResult(
        sale_id=sale.id,
        reference=sale.reference,
        total_minor=total,
    )

    updated = IdempotencyRecord.objects.filter(
        key=idempotency_key,
        request_fingerprint=fingerprint,
    ).update(
        response_payload={
            "sale_id": result.sale_id,
            "reference": str(result.reference),
            "total_minor": result.total_minor,
        }
    )

    if updated != 1:
        raise CheckoutError("failed to finalize idempotency record")

    return result
