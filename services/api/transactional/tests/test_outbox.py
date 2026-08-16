from datetime import timedelta
import threading
from unittest.mock import patch

import pytest
from django.core.management import call_command, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

from transactional.models import OutboxEvent
from transactional.outbox import OutboxIdempotencyConflict, enqueue_outbox_event
from transactional.outbox_dispatcher import dispatch_outbox_events
from transactional.payment_providers import PaymentProviderError


def make_event(*, key="outbox-001", event_type="payment.test", payload=None):
    return enqueue_outbox_event(
        event_type=event_type,
        aggregate_type="Payment",
        aggregate_id="42",
        idempotency_key=key,
        payload=payload or {"payment_id": 42},
    )


@pytest.mark.django_db

def test_enqueue_outbox_event_is_atomic_with_outer_transaction():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            make_event()
            raise RuntimeError("rollback")

    assert OutboxEvent.objects.count() == 0


@pytest.mark.django_db

def test_enqueue_outbox_event_is_idempotent():
    first = make_event()
    second = make_event()

    assert first.id == second.id
    assert OutboxEvent.objects.count() == 1


@pytest.mark.django_db

def test_enqueue_outbox_event_rejects_conflicting_payload_for_same_key():
    make_event()

    with pytest.raises(OutboxIdempotencyConflict):
        make_event(payload={"payment_id": 99})

    assert OutboxEvent.objects.count() == 1


@pytest.mark.django_db

def test_dispatcher_marks_successful_event_completed():
    event = make_event()
    seen = []

    result = dispatch_outbox_events(
        {"payment.test": lambda item: seen.append(item.payload)},
    )

    event.refresh_from_db()

    assert result.completed == 1
    assert result.failed == 0
    assert seen == [{"payment_id": 42}]
    assert event.status == OutboxEvent.Status.COMPLETED
    assert event.attempts == 1
    assert event.processed_at is not None
    assert event.locked_until is None


@pytest.mark.django_db

def test_dispatcher_records_failure_and_schedules_retry():
    event = make_event()

    result = dispatch_outbox_events(
        {"payment.test": lambda _event: (_ for _ in ()).throw(RuntimeError("boom"))},
    )

    event.refresh_from_db()

    assert result.completed == 0
    assert result.failed == 1
    assert event.status == OutboxEvent.Status.FAILED
    assert event.attempts == 1
    assert event.last_error == "boom"
    assert event.available_at > timezone.now()


@pytest.mark.django_db

def test_dispatcher_retries_failed_event_after_backoff():
    event = make_event()
    dispatch_outbox_events(
        {"payment.test": lambda _event: (_ for _ in ()).throw(RuntimeError("boom"))},
    )

    event.refresh_from_db()
    event.available_at = timezone.now() - timedelta(seconds=1)
    event.save(update_fields=["available_at"])

    seen = []
    result = dispatch_outbox_events(
        {"payment.test": lambda item: seen.append(item.id)},
    )

    event.refresh_from_db()

    assert result.completed == 1
    assert seen == [event.id]
    assert event.status == OutboxEvent.Status.COMPLETED
    assert event.attempts == 2


@pytest.mark.django_db(transaction=True)

def test_dispatcher_reclaims_expired_processing_lease():
    event = make_event()
    event.status = OutboxEvent.Status.PROCESSING
    event.attempts = 1
    event.locked_until = timezone.now() - timedelta(seconds=1)
    event.save(update_fields=["status", "attempts", "locked_until"])

    seen = []
    result = dispatch_outbox_events(
        {"payment.test": lambda item: seen.append(item.id)},
    )

    event.refresh_from_db()

    assert result.completed == 1
    assert seen == [event.id]
    assert event.status == OutboxEvent.Status.COMPLETED
    assert event.attempts == 2


@pytest.mark.django_db(transaction=True)

def test_concurrent_dispatchers_claim_event_once():
    make_event()
    barrier = threading.Barrier(2)
    processed = []
    errors = []

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = dispatch_outbox_events(
                {"payment.test": lambda event: processed.append(event.id)},
            )
            if result.failed:
                errors.append(result)
        except Exception as exc:
            errors.append(exc)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)
    assert not errors
    assert processed == [OutboxEvent.objects.get().id]
    assert OutboxEvent.objects.get().attempts == 1


@pytest.mark.django_db

def test_dispatch_command_surfaces_missing_provider_configuration_without_claiming_events():
    event = make_event(event_type="payment.test", key="outbox-provider-config-001")

    with patch(
        "transactional.management.commands.dispatch_outbox_events.PaystackProvider",
        side_effect=PaymentProviderError("PAYSTACK_SECRET_KEY is not configured"),
    ):
        with pytest.raises(CommandError, match="No outbox events were claimed"):
            call_command("dispatch_outbox_events")

    event.refresh_from_db()

    assert event.status == OutboxEvent.Status.PENDING
    assert event.attempts == 0
    assert event.locked_until is None
