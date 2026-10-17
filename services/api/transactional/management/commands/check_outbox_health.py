import json
import logging

from django.core.management.base import BaseCommand

from transactional.outbox_health import get_outbox_health

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Report transactional outbox queue and worker health."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero when the outbox is not healthy or the database is unreachable.",
        )

    def handle(self, *args, **options):
        snapshot = get_outbox_health()
        payload = snapshot.as_dict()
        logger.info("outbox health snapshot", extra=payload)
        self.stdout.write(json.dumps(payload, sort_keys=True))

        if options["strict"] and not snapshot.healthy:
            raise SystemExit(1)
