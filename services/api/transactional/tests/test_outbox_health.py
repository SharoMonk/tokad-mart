from datetime import timedelta

import pytest

from django.core.management import call_command
from django.utils import timezone

from transactional.models import OutboxEvent
from transactional.outbox_health import get_outbox_health


def make_event(*, status, created_at, available_at=None, locked_until=None):
    now = timezone.now()
    event = OutboxEvent.objects.create(
        event_type="TEST_EVENT",
        aggregate_type="Payment",
        aggregate_id="1",
        idempotency_key=f"health-{status}-{created_at.timestamp()}-{now.timestamp()}",
        payload={},
        status=status,
        available_at=available_at or now,
        locked_until=locked_until,
    )
    OutboxEvent.objects.filter(pk=event.pk).update(created_at=created_at)
    return event


@pytest.mark.django_db
def test_empty_outbox_is_healthy_and_ready():
    snapshot = get_outbox_health()

    assert snapshot.database_reachable is True
    assert snapshot.ready is True
    assert snapshot.healthy is True
    assert snapshot.queue_depth == 0
    assert snapshot.stale_processing == 0


@pytest.mark.django_db
def test_health_counts_ready_pending_retryable_and_processing_events():
    now = timezone.now()
    make_event(status=OutboxEvent.Status.PENDING, created_at=now - timedelta(seconds=20))
    make_event(status=OutboxEvent.Status.FAILED, created_at=now - timedelta(seconds=10))
    make_event(
        status=OutboxEvent.Status.PROCESSING,
        created_at=now - timedelta(seconds=5),
        locked_until=now + timedelta(seconds=30),
    )
    make_event(
        status=OutboxEvent.Status.COMPLETED,
        created_at=now - timedelta(seconds=60),
    )

    snapshot = get_outbox_health(now=now)

    assert snapshot.pending_ready == 1
    assert snapshot.retryable_ready == 1
    assert snapshot.processing == 1
    assert snapshot.queue_depth == 3
    assert snapshot.oldest_ready_age_seconds == pytest.approx(20, abs=1)


@pytest.mark.django_db
def test_stale_processing_marks_worker_unhealthy():
    now = timezone.now()
    make_event(
        status=OutboxEvent.Status.PROCESSING,
        created_at=now - timedelta(seconds=60),
        locked_until=now - timedelta(seconds=1),
    )

    snapshot = get_outbox_health(now=now)

    assert snapshot.ready is True
    assert snapshot.healthy is False
    assert snapshot.stale_processing == 1


@pytest.mark.django_db
def test_health_command_outputs_json(capsys):
    call_command("check_outbox_health")
    output = capsys.readouterr().out

    assert '"healthy": true' in output
    assert '"ready": true' in output
    assert '"queue_depth": 0' in output


@pytest.mark.django_db
def test_health_command_strict_mode_fails_for_stale_processing():
    now = timezone.now()
    make_event(
        status=OutboxEvent.Status.PROCESSING,
        created_at=now - timedelta(seconds=60),
        locked_until=now - timedelta(seconds=1),
    )

    with pytest.raises(SystemExit) as exc_info:
        call_command("check_outbox_health", "--strict")

    assert exc_info.value.code == 1
