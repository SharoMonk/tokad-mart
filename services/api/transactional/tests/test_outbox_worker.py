import logging
from unittest.mock import patch

import pytest

from django.core.management import call_command

from transactional.outbox_dispatcher import DispatchResult
from transactional.outbox_health import OutboxHealthSnapshot


@pytest.mark.django_db
def test_run_outbox_worker_once_delegates_to_dispatcher(caplog):
    snapshot = OutboxHealthSnapshot(
        generated_at=None,
        database_reachable=True,
        ready=True,
        healthy=True,
        queue_depth=3,
        pending_ready=2,
        retryable_ready=1,
        processing=0,
        stale_processing=0,
        oldest_ready_at=None,
        oldest_ready_age_seconds=None,
    )
    caplog.set_level(logging.INFO, logger="transactional.management.commands.run_outbox_worker")

    with (
        patch(
            "transactional.management.commands.run_outbox_worker.dispatch",
            return_value=DispatchResult(completed=2, failed=1, skipped=0),
        ) as dispatch,
        patch(
            "transactional.management.commands.run_outbox_worker.get_outbox_health",
            return_value=snapshot,
        ),
    ):
        call_command(
            "run_outbox_worker",
            "--once",
            "--limit",
            "7",
            "--lease-seconds",
            "45",
            "--poll-interval",
            "0",
        )

    dispatch.assert_called_once_with(
        limit=7,
        lease_seconds=45,
    )
    assert any(
        record.message == "outbox worker heartbeat"
        and getattr(record, "queue_depth", None) == 3
        and getattr(record, "cumulative_completed", None) == 2
        and getattr(record, "cumulative_failed", None) == 1
        for record in caplog.records
    )


@pytest.mark.django_db
def test_run_outbox_worker_rejects_negative_poll_interval():
    with pytest.raises(Exception, match="poll_interval must be non-negative"):
        call_command(
            "run_outbox_worker",
            "--once",
            "--poll-interval",
            "-1",
        )
