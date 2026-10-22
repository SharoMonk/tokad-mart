from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from django.db import connection
from django.db.models import Min, Q
from django.utils import timezone

from .models import OutboxEvent


@dataclass(frozen=True)
class OutboxHealthSnapshot:
    generated_at: datetime
    database_reachable: bool
    ready: bool
    healthy: bool
    queue_depth: int
    pending_ready: int
    retryable_ready: int
    processing: int
    stale_processing: int
    oldest_ready_at: datetime | None
    oldest_ready_age_seconds: float | None

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.isoformat()
        if self.oldest_ready_at is not None:
            payload["oldest_ready_at"] = self.oldest_ready_at.isoformat()
        return payload


def get_outbox_health(*, now=None) -> OutboxHealthSnapshot:
    current = now or timezone.now()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return OutboxHealthSnapshot(
            generated_at=current,
            database_reachable=False,
            ready=False,
            healthy=False,
            queue_depth=0,
            pending_ready=0,
            retryable_ready=0,
            processing=0,
            stale_processing=0,
            oldest_ready_at=None,
            oldest_ready_age_seconds=None,
        )

    ready_filter = Q(available_at__lte=current) & (
        Q(status=OutboxEvent.Status.PENDING)
        | Q(status=OutboxEvent.Status.FAILED)
    )
    pending_ready = OutboxEvent.objects.filter(
        available_at__lte=current,
        status=OutboxEvent.Status.PENDING,
    ).count()
    retryable_ready = OutboxEvent.objects.filter(
        available_at__lte=current,
        status=OutboxEvent.Status.FAILED,
    ).count()
    processing = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PROCESSING,
    ).count()
    stale_processing = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PROCESSING,
        locked_until__lt=current,
    ).count()
    oldest_ready_at = OutboxEvent.objects.filter(ready_filter).aggregate(
        oldest=Min("created_at"),
    )["oldest"]
    oldest_ready_age_seconds = None
    if oldest_ready_at is not None:
        oldest_ready_age_seconds = max(
            0.0,
            (current - oldest_ready_at).total_seconds(),
        )

    queue_depth = pending_ready + retryable_ready + processing
    return OutboxHealthSnapshot(
        generated_at=current,
        database_reachable=True,
        ready=True,
        healthy=stale_processing == 0,
        queue_depth=queue_depth,
        pending_ready=pending_ready,
        retryable_ready=retryable_ready,
        processing=processing,
        stale_processing=stale_processing,
        oldest_ready_at=oldest_ready_at,
        oldest_ready_age_seconds=oldest_ready_age_seconds,
    )
