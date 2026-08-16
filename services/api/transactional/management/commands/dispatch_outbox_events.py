from django.core.management.base import BaseCommand, CommandError

from transactional.outbox_dispatcher import dispatch_outbox_events
from transactional.payment_initiation import PAYMENT_INITIATION_REQUESTED_EVENT
from transactional.payment_initiation_outbox import make_payment_initiation_outbox_handler
from transactional.payment_outbox import REFUND_REQUESTED_EVENT, make_refund_outbox_handler
from transactional.payment_providers import PaymentProviderError
from transactional.providers.paystack import PaystackProvider


class Command(BaseCommand):
    help = "Dispatch pending transactional payment outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--lease-seconds", type=int, default=60)

    def handle(self, *args, **options):
        try:
            provider = PaystackProvider()
        except PaymentProviderError as exc:
            raise CommandError(
                f"outbox dispatch is blocked by provider configuration: {exc}. "
                "No outbox events were claimed; retry after configuring the provider."
            ) from exc

        result = dispatch_outbox_events(
            {
                REFUND_REQUESTED_EVENT: make_refund_outbox_handler(provider),
                PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(provider),
            },
            limit=options["limit"],
            lease_seconds=options["lease_seconds"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"completed={result.completed} failed={result.failed} skipped={result.skipped}"
            )
        )
