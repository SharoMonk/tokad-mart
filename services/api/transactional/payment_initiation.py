from __future__ import annotations

from django.db import connection, transaction
from django.utils import timezone

from .exceptions import (
    InvalidSaleStateError,
    PaymentError,
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    SaleNotFoundError,
)
from .models import OutboxEvent, Payment, Sale
from .outbox import enqueue_outbox_event
from .payment_providers import PaymentProvider
from .payment_services import (
    PaymentInitiationResult,
    _payment_initiation_result,
    _stable_provider_reference,
)

PAYMENT_INITIATION_REQUESTED_EVENT = "payment.initiation.requested"


def _lock_payment_key(key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"payment-initiation:{key}"],
        )


@transaction.atomic
def request_external_payment_initialization(
    *,
    sale_id: int,
    customer_email: str,
    provider: PaymentProvider,
    idempotency_key: str,
) -> PaymentInitiationResult:
    """Create a pending external payment and durably enqueue provider work."""
    customer_email = customer_email.strip()
    if not customer_email:
        raise PaymentError("customer email is required")

    _lock_payment_key(idempotency_key)

    try:
        sale = Sale.objects.select_for_update().get(id=sale_id)
    except Sale.DoesNotExist as exc:
        raise SaleNotFoundError("sale was not found") from exc

    existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if existing.sale_id != sale_id or existing.provider != provider.name:
            raise PaymentIdempotencyConflictError(
                "payment idempotency key was reused with a different request"
            )

        existing_email = (existing.provider_metadata or {}).get("customer_email")
        if existing_email and existing_email != customer_email:
            raise PaymentIdempotencyConflictError(
                "payment idempotency key was reused with a different request"
            )

        if existing.status != Payment.Status.PENDING:
            return _payment_initiation_result(existing)

        metadata = existing.provider_metadata or {}
        if not metadata.get("checkout_url") and not metadata.get("access_code"):
            event_key = f"payment-initiation:{idempotency_key}"
            event = OutboxEvent.objects.filter(idempotency_key=event_key).first()
            if event is None:
                enqueue_outbox_event(
                    event_type=PAYMENT_INITIATION_REQUESTED_EVENT,
                    aggregate_type="Payment",
                    aggregate_id=existing.id,
                    idempotency_key=event_key,
                    payload={
                        "payment_id": existing.id,
                        "provider": provider.name,
                        "customer_email": customer_email,
                    },
                )
            elif event.status == OutboxEvent.Status.FAILED:
                event.status = OutboxEvent.Status.PENDING
                event.available_at = timezone.now()
                event.locked_until = None
                event.last_error = ""
                event.save(
                    update_fields=[
                        "status",
                        "available_at",
                        "locked_until",
                        "last_error",
                        "updated_at",
                    ]
                )

        return _payment_initiation_result(existing)

    if sale.status != Sale.Status.PENDING_PAYMENT:
        raise InvalidSaleStateError(
            f"sale cannot accept payment in status {sale.status}"
        )

    provider_reference = _stable_provider_reference(
        provider.name,
        idempotency_key,
        sale.id,
    )

    payment = Payment.objects.create(
        sale=sale,
        provider=provider.name,
        provider_reference=provider_reference,
        idempotency_key=idempotency_key,
        method=Payment.Method.EXTERNAL,
        amount_minor=sale.total_minor,
        currency=sale.currency,
        status=Payment.Status.PENDING,
        provider_metadata={
            "customer_email": customer_email,
        },
    )

    enqueue_outbox_event(
        event_type=PAYMENT_INITIATION_REQUESTED_EVENT,
        aggregate_type="Payment",
        aggregate_id=payment.id,
        idempotency_key=f"payment-initiation:{idempotency_key}",
        payload={
            "payment_id": payment.id,
            "provider": provider.name,
            "customer_email": customer_email,
        },
    )

    return _payment_initiation_result(payment)


__all__ = ["PAYMENT_INITIATION_REQUESTED_EVENT", "request_external_payment_initialization"]
