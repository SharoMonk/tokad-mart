from __future__ import annotations

from typing import Callable

from django.db import transaction
from django.utils import timezone

from .exceptions import PaymentError
from .models import AuditEvent, OutboxEvent, Payment
from .payment_providers import PaymentIntent, PaymentProvider, PaymentProviderError

from .payment_initiation import PAYMENT_INITIATION_REQUESTED_EVENT


def make_payment_initiation_outbox_handler(
    provider: PaymentProvider,
) -> Callable[[OutboxEvent], None]:
    """Create an outbox handler for external payment initiation."""

    def handle(event: OutboxEvent) -> None:
        if event.event_type != PAYMENT_INITIATION_REQUESTED_EVENT:
            raise ValueError(f"unsupported payment outbox event: {event.event_type}")

        payment_id = int(event.payload["payment_id"])
        customer_email = str(event.payload["customer_email"]).strip()

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id)

            if payment.provider != provider.name:
                raise PaymentError("payment provider does not match outbox provider")

            if payment.status != Payment.Status.PENDING:
                return

            provider_reference = payment.provider_reference
            amount_minor = payment.amount_minor
            currency = payment.currency

        try:
            intent: PaymentIntent = provider.initiate_payment(
                amount_minor=amount_minor,
                currency=currency,
                reference=provider_reference,
                customer_email=customer_email,
            )
        except PaymentProviderError as exc:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment_id)
                payment.provider_metadata = {
                    **(payment.provider_metadata or {}),
                    "error": str(exc),
                    "last_attempted_at": timezone.now().isoformat(),
                }
                payment.save(update_fields=["provider_metadata"])
            raise

        if intent.provider != provider.name:
            raise PaymentProviderError(
                "provider returned an unexpected provider name"
            )
        if intent.provider_reference != provider_reference:
            raise PaymentProviderError(
                "provider returned an unexpected transaction reference"
            )
        if intent.amount_minor != amount_minor:
            raise PaymentProviderError(
                "provider returned an unexpected transaction amount"
            )
        if intent.currency.upper() != currency.upper():
            raise PaymentProviderError(
                "provider returned an unexpected transaction currency"
            )

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id)

            if payment.status != Payment.Status.PENDING:
                return

            payment.provider_metadata = {
                **(payment.provider_metadata or {}),
                "checkout_url": intent.checkout_url,
                "access_code": intent.access_code,
                "initialized_at": timezone.now().isoformat(),
            }
            payment.save(update_fields=["provider_metadata"])

            AuditEvent.objects.create(
                actor="system",
                action="payment.initiated",
                entity_type="Payment",
                entity_reference=str(payment.id),
                metadata={
                    "sale_id": payment.sale_id,
                    "provider": payment.provider,
                    "provider_reference": payment.provider_reference,
                    "amount_minor": payment.amount_minor,
                    "currency": payment.currency,
                },
            )

    return handle


__all__ = ["make_payment_initiation_outbox_handler"]
