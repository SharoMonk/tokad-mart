from __future__ import annotations

from typing import Callable

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .exceptions import PaymentError
from .models import AuditEvent, OutboxEvent, Payment, PaymentRefund
from .payment_providers import PaymentProvider, PaymentProviderError

REFUND_REQUESTED_EVENT = "payment.refund.requested"


def make_refund_outbox_handler(
    provider: PaymentProvider,
) -> Callable[[OutboxEvent], None]:
    """Create an outbox handler for refund events for one provider."""

    def handle(event: OutboxEvent) -> None:
        if event.event_type != REFUND_REQUESTED_EVENT:
            raise ValueError(f"unsupported payment outbox event: {event.event_type}")

        refund_id = int(event.payload["refund_id"])

        with transaction.atomic():
            refund = (
                PaymentRefund.objects
                .select_for_update()
                .select_related("payment")
                .get(id=refund_id)
            )

            if refund.status == PaymentRefund.Status.SUCCEEDED:
                return

            if refund.provider != provider.name:
                raise PaymentError("refund provider does not match outbox provider")

            payment_id = refund.payment_id
            provider_reference = refund.provider_reference
            amount_minor = refund.amount_minor

        try:
            provider.refund_payment(
                provider_reference=provider_reference,
                amount_minor=amount_minor,
            )
        except PaymentProviderError as exc:
            with transaction.atomic():
                refund = PaymentRefund.objects.select_for_update().get(id=refund_id)
                refund.provider_metadata = {
                    **(refund.provider_metadata or {}),
                    "error": str(exc),
                    "last_attempted_at": timezone.now().isoformat(),
                }
                refund.save(update_fields=["provider_metadata"])
            raise

        with transaction.atomic():
            refund = PaymentRefund.objects.select_for_update().get(id=refund_id)

            if refund.status == PaymentRefund.Status.SUCCEEDED:
                return

            refund.status = PaymentRefund.Status.SUCCEEDED
            refund.provider_metadata = {
                **(refund.provider_metadata or {}),
                "processed_at": timezone.now().isoformat(),
            }
            refund.save(update_fields=["status", "provider_metadata"])

            payment = Payment.objects.select_for_update().get(id=payment_id)
            refunded_total = (
                PaymentRefund.objects.filter(
                    payment=payment,
                    status=PaymentRefund.Status.SUCCEEDED,
                ).aggregate(total=Sum("amount_minor"))["total"]
                or 0
            )
            full_refund = refunded_total >= payment.amount_minor

            if full_refund and payment.status != Payment.Status.REFUNDED:
                payment.status = Payment.Status.REFUNDED
                payment.save(update_fields=["status"])

            AuditEvent.objects.create(
                actor="system",
                action="payment.refunded",
                entity_type="PaymentRefund",
                entity_reference=str(refund.id),
                metadata={
                    "payment_id": payment.id,
                    "provider": payment.provider,
                    "provider_reference": payment.provider_reference,
                    "amount_minor": refund.amount_minor,
                    "currency": refund.currency,
                    "full_refund": full_refund,
                },
            )

    return handle


__all__ = ["REFUND_REQUESTED_EVENT", "make_refund_outbox_handler"]
