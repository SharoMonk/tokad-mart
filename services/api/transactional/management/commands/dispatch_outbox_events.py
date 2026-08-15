from django.core.management.base import BaseCommand

from transactional.outbox_dispatcher import dispatch_outbox_events
from transactional.payment_outbox import REFUND_REQUESTED_EVENT, make_refund_outbox_handler
from transactional.paystack import PaystackProvider


class Command(BaseCommand):
    help = "Dispatch pending transactional payment outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--lease-seconds", type=int, default=60)

    def handle(self, *args, **options):
        result = dispatch_outbox_events(
            {
                REFUND_REQUESTED_EVENT: make_refund_outbox_handler(PaystackProvider()),
            },
            limit=options["limit"],
            lease_seconds=options["lease_seconds"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"completed={result.completed} failed={result.failed} skipped={result.skipped}"
            )
        )
