from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from transactional.models import OutboxEvent
from transactional.outbox import enqueue_outbox_event
from transactional.payment_providers import PaymentProviderError


@pytest.mark.django_db(transaction=True)
def test_dispatch_command_does_not_initialize_provider_when_queue_is_empty(capsys):
    with patch(
        "transactional.management.commands.dispatch_outbox_events.PaystackProvider"
    ) as provider_cls:
        call_command("dispatch_outbox_events")

    provider_cls.assert_not_called()
    assert OutboxEvent.objects.count() == 0
    assert "completed=0 failed=0 skipped=0" in capsys.readouterr().out


@pytest.mark.django_db(transaction=True)
def test_dispatch_command_records_missing_provider_configuration_as_retryable_failure(
    capsys,
):
    event = enqueue_outbox_event(
        event_type="payment.initiation.requested",
        aggregate_type="Payment",
        aggregate_id="42",
        idempotency_key="payment-initiation-configuration-001",
        payload={"payment_id": 42},
    )

    with patch(
        "transactional.management.commands.dispatch_outbox_events.PaystackProvider",
        side_effect=PaymentProviderError("PAYSTACK_SECRET_KEY is not configured"),
    ):
        call_command("dispatch_outbox_events")

    event.refresh_from_db()

    assert event.status == OutboxEvent.Status.FAILED
    assert event.attempts == 1
    assert event.locked_until is None
    assert event.available_at > timezone.now()
    assert "PAYSTACK_SECRET_KEY is not configured" in event.last_error
    assert "completed=0 failed=1 skipped=0" in capsys.readouterr().out
