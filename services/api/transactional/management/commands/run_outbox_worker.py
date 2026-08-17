import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError

from transactional.management.commands.dispatch_outbox_events import Command as DispatchCommand

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

        def request_shutdown(signum, _frame):
            nonlocal stop
            stop = True
            logger.info("outbox worker shutdown requested", extra={"signal": signum})

        previous_sigterm = signal.getsignal(signal.SIGTERM)
        previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)

        dispatcher = DispatchCommand()
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
                dispatcher.handle(
                    limit=options["limit"],
                    lease_seconds=options["lease_seconds"],
                )

                if options["once"] or stop:
                    break

                time.sleep(poll_interval)
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
            signal.signal(signal.SIGINT, previous_sigint)
            logger.info("outbox worker stopped")
            self.stdout.write("outbox worker stopped")
