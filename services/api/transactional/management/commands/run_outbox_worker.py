import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError

from transactional.management.commands.dispatch_outbox_events import dispatch
from transactional.outbox_health import get_outbox_health

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Continuously dispatch pending transactional payment outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--lease-seconds", type=int, default=60)
        parser.add_argument("--poll-interval", type=float, default=2.0)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        poll_interval = options["poll_interval"]
        if poll_interval < 0:
            raise CommandError("poll_interval must be non-negative")

        stop = False
        cycles = 0
        cumulative_completed = 0
        cumulative_failed = 0
        cumulative_skipped = 0

        def request_shutdown(signum, _frame):
            nonlocal stop
            stop = True
            logger.info("outbox worker shutdown requested", extra={"signal": signum})

        previous_sigterm = signal.getsignal(signal.SIGTERM)
        previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)

        self.stdout.write("outbox worker started")
        logger.info(
            "outbox worker started",
            extra={
                "limit": options["limit"],
                "lease_seconds": options["lease_seconds"],
                "poll_interval": poll_interval,
            },
        )

        try:
            while not stop:
                result = dispatch(
                    limit=options["limit"],
                    lease_seconds=options["lease_seconds"],
                )
                cycles += 1
                cumulative_completed += result.completed
                cumulative_failed += result.failed
                cumulative_skipped += result.skipped

                snapshot = get_outbox_health()
                logger.info(
                    "outbox worker heartbeat",
                    extra={
                        "cycle": cycles,
                        "completed": result.completed,
                        "failed": result.failed,
                        "skipped": result.skipped,
                        "cumulative_completed": cumulative_completed,
                        "cumulative_failed": cumulative_failed,
                        "cumulative_skipped": cumulative_skipped,
                        "queue_depth": snapshot.queue_depth,
                        "pending_ready": snapshot.pending_ready,
                        "retryable_ready": snapshot.retryable_ready,
                        "processing": snapshot.processing,
                        "stale_processing": snapshot.stale_processing,
                        "oldest_ready_age_seconds": snapshot.oldest_ready_age_seconds,
                        "database_reachable": snapshot.database_reachable,
                        "healthy": snapshot.healthy,
                    },
                )

                if options["once"] or stop:
                    break

                time.sleep(poll_interval)
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
            signal.signal(signal.SIGINT, previous_sigint)
            logger.info(
                "outbox worker stopped",
                extra={
                    "cycles": cycles,
                    "cumulative_completed": cumulative_completed,
                    "cumulative_failed": cumulative_failed,
                    "cumulative_skipped": cumulative_skipped,
                },
            )
            self.stdout.write("outbox worker stopped")
