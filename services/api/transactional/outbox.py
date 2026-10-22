from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import OutboxEvent


class OutboxIdempotencyConflict(ValueError):
    """Raised when an outbox key is reused with different event data."""


def enqueue_outbox_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str | int,
    idempotency_key: str,
    payload: dict[str, Any],
    available_at=None,
) -> OutboxEvent:
    """Create an outbox event inside the caller's database transaction.

    The event is durably committed or rolled back with the surrounding
    transaction. Reusing an idempotency key with the same event data is safe.
    """
    if available_at is None:
        available_at = timezone.now()

    with transaction.atomic():
        existing = OutboxEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if (
                existing.event_type != event_type
                or existing.aggregate_type != aggregate_type
                or existing.aggregate_id != str(aggregate_id)
                or existing.payload != payload
            ):
                raise OutboxIdempotencyConflict(
                    "outbox idempotency key was reused with different event data"
                )
            return existing

        return OutboxEvent.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            idempotency_key=idempotency_key,
            payload=payload,
            available_at=available_at,
        )


def retry_available_at(attempts: int, *, now=None):
    """Return a bounded exponential-backoff time for a failed event."""
    if now is None:
        now = timezone.now()
    delay_seconds = min(300, 2 ** max(0, attempts - 1))
    return now + timedelta(seconds=delay_seconds)
