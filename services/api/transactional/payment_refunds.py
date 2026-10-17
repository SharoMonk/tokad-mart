from dataclasses import dataclass

from django.db import connection, transaction
from django.db.models import Sum

from .exceptions import (
    InvalidSaleStateError,
    PaymentAmountMismatchError,
    PaymentError,
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
)
from .models import Payment, PaymentRefund
from .outbox import enqueue_outbox_event
from .payment_outbox import REFUND_REQUESTED_EVENT
from .payment_providers import PaymentProvider, VerifiedPayment


@dataclass(frozen=True)
class RefundResult:
    refund_id: int
    payment_id: int
    amount_minor: int
    currency: str
    status: str
    provider: str


@dataclass(frozen=True)
class ReconciliationResult:
    payment_id: int
    provider: str
    provider_reference: str
    local_status: str
    provider_status: str
    amount_minor: int
    currency: str
    matches: bool


def _lock_refund_key(key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"refund:{key}"],
        )


@transaction.atomic
def request_refund(
    *,
    payment_id: int,
    amount_minor: int | None,
    provider: PaymentProvider,
    idempotency_key: str,
) -> RefundResult:
    """Create an idempotent refund request and durably enqueue provider work."""
    _lock_refund_key(idempotency_key)

    existing = PaymentRefund.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if existing.payment_id != payment_id or (
            amount_minor is not None and existing.amount_minor != amount_minor
        ):
            raise PaymentIdempotencyConflictError(
                "refund idempotency key was reused with a different request"
            )
        return RefundResult(
            refund_id=existing.id,
            payment_id=existing.payment_id,
            amount_minor=existing.amount_minor,
            currency=existing.currency,
            status=existing.status,
            provider=existing.provider,
        )

    try:
        payment = Payment.objects.select_for_update().get(id=payment_id)
    except Payment.DoesNotExist as exc:
        raise PaymentNotFoundError("payment was not found") from exc

    if payment.status != Payment.Status.SUCCEEDED:
        raise InvalidSaleStateError(
            f"payment cannot be refunded in status {payment.status}"
        )

    if provider.name != payment.provider:
        raise PaymentError("refund provider does not match payment provider")

    already_refunded = (
        PaymentRefund.objects.filter(
            payment=payment,
            status__in=[
                PaymentRefund.Status.REQUESTED,
                PaymentRefund.Status.SUCCEEDED,
            ],
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )

    remaining = payment.amount_minor - already_refunded
    refund_amount = remaining if amount_minor is None else amount_minor

    if refund_amount <= 0 or refund_amount > remaining:
        raise PaymentAmountMismatchError(
            "refund amount must be positive and cannot exceed the remaining refundable amount"
        )

    refund = PaymentRefund.objects.create(
        payment=payment,
        provider=provider.name,
        provider_reference=payment.provider_reference,
        idempotency_key=idempotency_key,
        amount_minor=refund_amount,
        currency=payment.currency,
        status=PaymentRefund.Status.REQUESTED,
    )

    enqueue_outbox_event(
        event_type=REFUND_REQUESTED_EVENT,
        aggregate_type="PaymentRefund",
        aggregate_id=refund.id,
        idempotency_key=f"payment-refund:{idempotency_key}",
        payload={
            "refund_id": refund.id,
            "payment_id": payment.id,
            "provider": provider.name,
        },
    )

    return RefundResult(
        refund_id=refund.id,
        payment_id=refund.payment_id,
        amount_minor=refund.amount_minor,
        currency=refund.currency,
        status=refund.status,
        provider=refund.provider,
    )


@transaction.atomic
def reconcile_payment(
    *,
    payment_id: int,
    provider: PaymentProvider,
) -> ReconciliationResult:
    """Compare local payment state with the provider without mutating it."""
    try:
        payment = Payment.objects.select_for_update().get(id=payment_id)
    except Payment.DoesNotExist as exc:
        raise PaymentNotFoundError("payment was not found") from exc

    if provider.name != payment.provider:
        raise PaymentError("reconciliation provider does not match payment provider")

    verified: VerifiedPayment = provider.verify_payment(
        provider_reference=payment.provider_reference,
    )

    amount_matches = verified.amount_minor == payment.amount_minor
    currency_matches = verified.currency.upper() == payment.currency.upper()
    provider_status = "SUCCEEDED" if verified.succeeded else "NOT_SUCCEEDED"

    return ReconciliationResult(
        payment_id=payment.id,
        provider=payment.provider,
        provider_reference=payment.provider_reference,
        local_status=payment.status,
        provider_status=provider_status,
        amount_minor=verified.amount_minor,
        currency=verified.currency,
        matches=amount_matches and currency_matches and (
            (payment.status == Payment.Status.SUCCEEDED and verified.succeeded)
            or (payment.status != Payment.Status.SUCCEEDED and not verified.succeeded)
        ),
    )
