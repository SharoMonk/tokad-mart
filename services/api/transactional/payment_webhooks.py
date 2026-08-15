from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .exceptions import PaymentError, PaymentNotFoundError
from .models import Payment, PaymentWebhookEvent
from .payment_providers import VerifiedPayment, validate_verified_payment
from .payment_services import finalize_paid_sale


class PaymentWebhookError(PaymentError):
    """Raised when a provider webhook cannot be processed safely."""


@dataclass(frozen=True)
class WebhookResult:
    event_id: str
    payment_id: int
    payment_status: str
    sale_id: int
    sale_status: str
    already_processed: bool


@transaction.atomic
def process_payment_webhook(
    *,
    provider: str,
    event_id: str,
    provider_reference: str,
    verified: VerifiedPayment,
) -> WebhookResult:
    """Apply a verified provider event exactly once."""
    existing_event = PaymentWebhookEvent.objects.filter(
        provider=provider,
        event_id=event_id,
    ).first()

    if existing_event is not None:
        payment = Payment.objects.get(id=existing_event.payment_id)
        return WebhookResult(
            event_id=event_id,
            payment_id=payment.id,
            payment_status=payment.status,
            sale_id=payment.sale_id,
            sale_status=payment.sale.status,
            already_processed=True,
        )

    try:
        payment = Payment.objects.select_for_update().select_related("sale").get(
            provider=provider,
            provider_reference=provider_reference,
        )
    except Payment.DoesNotExist as exc:
        raise PaymentNotFoundError("payment was not found for provider reference") from exc

    if verified.provider != provider:
        raise PaymentWebhookError("webhook provider does not match payment provider")

    if verified.provider_reference != provider_reference:
        raise PaymentWebhookError("webhook provider reference does not match payment")

    try:
        validate_verified_payment(
            expected_amount_minor=payment.amount_minor,
            expected_currency=payment.currency,
            verified=verified,
        )
    except Exception as exc:
        raise PaymentWebhookError(str(exc)) from exc

    event = PaymentWebhookEvent.objects.create(
        provider=provider,
        event_id=event_id,
        payment=payment,
        payload={},
    )

    if payment.status == Payment.Status.SUCCEEDED:
        return WebhookResult(
            event_id=event_id,
            payment_id=payment.id,
            payment_status=payment.status,
            sale_id=payment.sale_id,
            sale_status=payment.sale.status,
            already_processed=False,
        )

    if payment.status != Payment.Status.PENDING:
        raise PaymentWebhookError(
            f"payment cannot transition from status {payment.status}"
        )

    payment.status = Payment.Status.SUCCEEDED
    payment.save(update_fields=["status"])

    completed = finalize_paid_sale(
        sale_id=payment.sale_id,
        payment_id=payment.id,
    )

    sale = payment.sale
    event.processed_at = timezone.now()
    event.payload = {
        "provider": provider,
        "provider_reference": provider_reference,
        "payment_id": payment.id,
        "sale_id": completed.sale_id,
    }
    event.save(update_fields=["processed_at", "payload"])

    return WebhookResult(
        event_id=event_id,
        payment_id=payment.id,
        payment_status=payment.status,
        sale_id=completed.sale_id,
        sale_status=sale.status,
        already_processed=False,
    )
