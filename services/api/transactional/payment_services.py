from dataclasses import dataclass
from uuid import UUID

from django.db import connection, transaction
from django.utils import timezone

from .models import (
    AuditEvent,
    InventoryItem,
    InventoryMovement,
    Payment,
    Product,
    Sale,
    SaleLine,
)
from .services import (
    CheckoutError,
    CheckoutLine,
    CheckoutResult,
    _fingerprint,
)


class PaymentError(Exception):
    """Raised when a payment operation violates a domain invariant."""


@dataclass(frozen=True)
class PaymentResult:
    payment_id: int
    sale_id: int
    amount_minor: int
    currency: str
    status: str
    provider_reference: str


@dataclass(frozen=True)
class POSSaleResult:
    sale_id: int
    reference: UUID
    payment_id: int
    total_minor: int
    currency: str
    sale_status: str
    payment_status: str


def _lock_payment_key(key: str) -> None:
    """Serialize payment attempts using the same idempotency key."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"payment:{key}"],
        )


def _payment_result(payment: Payment) -> PaymentResult:
    return PaymentResult(
        payment_id=payment.id,
        sale_id=payment.sale_id,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        status=payment.status,
        provider_reference=payment.provider_reference,
    )


@transaction.atomic
def create_pending_sale(
    *,
    lines: list[CheckoutLine],
    location_code: str,
    currency: str,
    idempotency_key: str,
) -> CheckoutResult:
    """Create a sale awaiting payment without consuming inventory."""
    if not lines:
        raise CheckoutError("sale requires at least one line")

    if any(line.quantity <= 0 for line in lines):
        raise CheckoutError("line quantity must be positive")

    fingerprint = _fingerprint(lines, location_code, currency)
    _lock_payment_key(f"sale:{idempotency_key}")

    from .models import IdempotencyRecord

    existing = IdempotencyRecord.objects.filter(
        key=f"sale:{idempotency_key}",
    ).first()

    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise CheckoutError(
                "sale idempotency key was reused with a different request"
            )

        payload = existing.response_payload
        if not payload:
            raise CheckoutError("sale is currently being processed")

        return CheckoutResult(
            sale_id=int(payload["sale_id"]),
            reference=UUID(str(payload["reference"])),
            total_minor=int(payload["total_minor"]),
        )

    product_ids = sorted({line.product_id for line in lines})
    products = {
        product.id: product
        for product in Product.objects.filter(
            id__in=product_ids,
            is_active=True,
        )
    }

    if len(products) != len(product_ids):
        raise CheckoutError("one or more products are unavailable")

    if any(product.currency != currency for product in products.values()):
        raise CheckoutError("sale currency does not match product currency")

    inventory = {
        item.product_id: item
        for item in InventoryItem.objects.filter(
            product_id__in=product_ids,
            location_code=location_code,
        )
    }

    if len(inventory) != len(product_ids):
        raise CheckoutError("inventory record is missing")

    total = 0
    resolved: list[tuple[Product, int, int]] = []

    for line in lines:
        product = products[line.product_id]
        line_total = product.unit_price_minor * line.quantity
        total += line_total
        resolved.append((product, line.quantity, line_total))

    sale = Sale.objects.create(
        reference=__import__("uuid").uuid4(),
        location_code=location_code,
        currency=currency,
        subtotal_minor=total,
        total_minor=total,
        status=Sale.Status.PENDING_PAYMENT,
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

    IdempotencyRecord.objects.create(
        key=f"sale:{idempotency_key}",
        request_fingerprint=fingerprint,
        response_payload={
            "sale_id": sale.id,
            "reference": str(sale.reference),
            "total_minor": sale.total_minor,
        },
    )

    return CheckoutResult(
        sale_id=sale.id,
        reference=sale.reference,
        total_minor=total,
    )


@transaction.atomic
def record_successful_payment(
    *,
    sale_id: int,
    amount_minor: int,
    currency: str,
    method: str,
    provider: str,
    provider_reference: str,
    idempotency_key: str,
) -> PaymentResult:
    """Record a successful payment without consuming inventory."""
    if amount_minor <= 0:
        raise PaymentError("payment amount must be positive")

    _lock_payment_key(idempotency_key)

    existing = Payment.objects.filter(
        idempotency_key=idempotency_key,
    ).first()

    if existing is not None:
        if (
            existing.sale_id != sale_id
            or existing.amount_minor != amount_minor
            or existing.currency != currency
            or existing.method != method
            or existing.provider != provider
        ):
            raise PaymentError(
                "payment idempotency key was reused with a different request"
            )
        return _payment_result(existing)

    sale = Sale.objects.select_for_update().get(id=sale_id)

    if sale.status != Sale.Status.PENDING_PAYMENT:
        raise PaymentError(
            f"sale cannot accept payment in status {sale.status}"
        )

    if currency != sale.currency:
        raise PaymentError("payment currency does not match sale currency")

    if amount_minor != sale.total_minor:
        raise PaymentError("payment amount does not match sale total")

    payment = Payment.objects.create(
        sale=sale,
        provider=provider,
        provider_reference=provider_reference,
        idempotency_key=idempotency_key,
        method=method,
        amount_minor=amount_minor,
        currency=currency,
        status=Payment.Status.SUCCEEDED,
    )

    AuditEvent.objects.create(
        actor="system",
        action="payment.succeeded",
        entity_type="Payment",
        entity_reference=str(payment.id),
        metadata={
            "sale_id": sale.id,
            "provider": provider,
            "method": method,
            "amount_minor": amount_minor,
            "currency": currency,
        },
    )

    return _payment_result(payment)


@transaction.atomic
def finalize_paid_sale(
    *,
    sale_id: int,
    payment_id: int,
) -> CheckoutResult:
    """Consume inventory and complete a sale after successful payment."""
    sale = Sale.objects.select_for_update().get(id=sale_id)

    if sale.status == Sale.Status.COMPLETED:
        return CheckoutResult(
            sale_id=sale.id,
            reference=sale.reference,
            total_minor=sale.total_minor,
        )

    if sale.status != Sale.Status.PENDING_PAYMENT:
        raise PaymentError(
            f"sale cannot be finalized in status {sale.status}"
        )

    payment = Payment.objects.select_for_update().get(
        id=payment_id,
        sale=sale,
    )

    if payment.status != Payment.Status.SUCCEEDED:
        raise PaymentError("sale cannot be finalized without a successful payment")

    if payment.amount_minor != sale.total_minor:
        raise PaymentError("successful payment amount does not match sale total")

    if payment.currency != sale.currency:
        raise PaymentError("successful payment currency does not match sale currency")

    lines = list(
        SaleLine.objects.select_related("product").filter(sale=sale).order_by("product_id", "id")
    )

    if not lines:
        raise PaymentError("sale has no sale lines")

    quantities: dict[int, int] = {}
    for line in lines:
        quantities[line.product_id] = quantities.get(line.product_id, 0) + line.quantity

    product_ids = sorted(quantities)
    inventory = {
        item.product_id: item
        for item in InventoryItem.objects.select_for_update().filter(
            product_id__in=product_ids,
            location_code=sale.location_code,
        ).order_by("product_id")
    }

    if len(inventory) != len(product_ids):
        raise PaymentError("inventory record is missing")

    for product_id in product_ids:
        item = inventory[product_id]
        quantity = quantities[product_id]
        if item.quantity < quantity:
            raise PaymentError(
                f"insufficient stock for product {product_id}"
            )

    for product_id in product_ids:
        item = inventory[product_id]
        quantity = quantities[product_id]
        item.quantity -= quantity
        item.save(update_fields=["quantity"])

        InventoryMovement.objects.create(
            inventory_item=item,
            quantity_delta=-quantity,
            reason=InventoryMovement.Reason.SALE,
            reference=str(sale.reference),
        )

    sale.status = Sale.Status.COMPLETED
    sale.completed_at = timezone.now()
    sale.save(update_fields=["status", "completed_at"])

    AuditEvent.objects.create(
        actor="system",
        action="sale.completed",
        entity_type="Sale",
        entity_reference=str(sale.reference),
        metadata={
            "total_minor": sale.total_minor,
            "currency": sale.currency,
            "payment_id": payment.id,
        },
    )

    return CheckoutResult(
        sale_id=sale.id,
        reference=sale.reference,
        total_minor=sale.total_minor,
    )


@transaction.atomic
def process_pos_cash_sale(
    *,
    lines: list[CheckoutLine],
    location_code: str,
    currency: str,
    amount_minor: int,
    sale_idempotency_key: str,
    payment_idempotency_key: str,
    provider_reference: str,
) -> POSSaleResult:
    """Run the complete cash POS flow in one database transaction."""
    sale = create_pending_sale(
        lines=lines,
        location_code=location_code,
        currency=currency,
        idempotency_key=sale_idempotency_key,
    )

    payment = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=amount_minor,
        currency=currency,
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference=provider_reference,
        idempotency_key=payment_idempotency_key,
    )

    completed = finalize_paid_sale(
        sale_id=sale.sale_id,
        payment_id=payment.payment_id,
    )

    return POSSaleResult(
        sale_id=completed.sale_id,
        reference=completed.reference,
        payment_id=payment.payment_id,
        total_minor=completed.total_minor,
        currency=currency,
        sale_status=Sale.Status.COMPLETED,
        payment_status=Payment.Status.SUCCEEDED,
    )
