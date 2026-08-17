from unittest.mock import patch

import pytest

from django.core.management import call_command


@pytest.mark.django_db

def test_run_outbox_worker_once_delegates_to_dispatcher():
    with patch(
        "transactional.management.commands.run_outbox_worker.DispatchCommand.handle"
    ) as handle:
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

    handle.assert_called_once_with(
        limit=7,
        lease_seconds=45,
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
