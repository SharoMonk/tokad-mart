from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import OutboxEvent
from .outbox import retry_available_at

OutboxHandler = Callable[[OutboxEvent], None]


@dataclass(frozen=True)
class DispatchResult:
    completed: int = 0
    failed: int = 0
    skipped: int = 0


def _claim_event(*, now, lease_seconds: int) -> OutboxEvent | None:
    with transaction.atomic():
        event = (
            OutboxEvent.objects
            .select_for_update(skip_locked=True)
            .filter(available_at__lte=now)
            .filter(
                Q(status=OutboxEvent.Status.PENDING)
                | Q(status=OutboxEvent.Status.FAILED)
                | (
                    Q(status=OutboxEvent.Status.PROCESSING)
                    & Q(locked_until__lt=now)
                )
            )
            .order_by("id")
            .first()
        )
        if event is None:
            return None

        event.status = OutboxEvent.Status.PROCESSING
        event.attempts += 1
        event.locked_until = now + timedelta(seconds=lease_seconds)
        event.last_error = ""
        event.save(
            update_fields=[
                "status",
                "attempts",
                "locked_until",
                "last_error",
                "updated_at",
            ]
        )
        return event


def _mark_completed(event_id: int, *, now) -> None:
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().get(id=event_id)
        event.status = OutboxEvent.Status.COMPLETED
        event.processed_at = now
        event.locked_until = None
        event.last_error = ""
        event.save(
            update_fields=[
                "status",
                "processed_at",
                "locked_until",
                "last_error",
                "updated_at",
            ]
        )


def _mark_failed(event_id: int, error: Exception, *, now) -> None:
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().get(id=event_id)
        event.status = OutboxEvent.Status.FAILED
        event.available_at = retry_available_at(event.attempts, now=now)
        event.locked_until = None
        event.last_error = str(error)
        event.save(
            update_fields=[
                "status",
                "available_at",
                "locked_until",
                "last_error",
                "updated_at",
            ]
        )


def dispatch_outbox_events(
    handlers: dict[str, OutboxHandler],
    *,
    limit: int = 10,
    lease_seconds: int = 60,
    now=None,
) -> DispatchResult:
    """Claim and dispatch up to ``limit`` durable outbox events.

    Handlers run outside the claiming transaction. A crash after claiming
    leaves a leased PROCESSING event that can be reclaimed after the lease.
    Handlers must therefore be idempotent using the event's idempotency key.
    """
    if limit <= 0:
        return DispatchResult()
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    completed = failed = skipped = 0
    current = now or timezone.now()

    for _ in range(limit):
        event = _claim_event(now=current, lease_seconds=lease_seconds)
        if event is None:
            break

        handler = handlers.get(event.event_type)
        if handler is None:
            _mark_failed(
                event.id,
                RuntimeError(f"no handler registered for {event.event_type}"),
                now=current,
            )
            failed += 1
            continue

        try:
            handler(event)
        except Exception as exc:
            _mark_failed(event.id, exc, now=current)
            failed += 1
        else:
            _mark_completed(event.id, now=timezone.now())
            completed += 1

    return DispatchResult(
        completed=completed,
        failed=failed,
        skipped=skipped,
    )
