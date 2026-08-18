import logging

from django.core.management.base import BaseCommand, CommandError

from transactional.outbox_dispatcher import DispatchResult, dispatch_outbox_events
from transactional.payment_initiation import PAYMENT_INITIATION_REQUESTED_EVENT
from transactional.payment_initiation_outbox import make_payment_initiation_outbox_handler
from transactional.payment_outbox import REFUND_REQUESTED_EVENT, make_refund_outbox_handler
from transactional.payment_providers import PaymentProviderError
from transactional.providers.paystack import PaystackProvider

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dispatch pending transactional payment outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--lease-seconds", type=int, default=60)

    def handle(self, *args, **options) -> None:
        result = dispatch(
            limit=options["limit"],
            lease_seconds=options["lease_seconds"],
        )

        logger.info(
            "outbox dispatch completed",
            extra={
                "completed": result.completed,
                "failed": result.failed,
                "skipped": result.skipped,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"completed={result.completed} failed={result.failed} skipped={result.skipped}"
            )
        )

    @staticmethod
    def _provider():
        try:
            return PaystackProvider()
        except PaymentProviderError as exc:
            raise CommandError(
                f"outbox provider configuration is unavailable: {exc}. "
                "The claimed event will be recorded as failed and retried after backoff."
            ) from exc

    @classmethod
    def _make_refund_handler(cls, event):
        return make_refund_outbox_handler(cls._provider())(event)

    @classmethod
    def _make_payment_initiation_handler(cls, event):
        return make_payment_initiation_outbox_handler(cls._provider())(event)


def dispatch(*, limit: int = 10, lease_seconds: int = 60) -> DispatchResult:
    return dispatch_outbox_events(
        {
            REFUND_REQUESTED_EVENT: Command._make_refund_handler,
            PAYMENT_INITIATION_REQUESTED_EVENT: Command._make_payment_initiation_handler,
        },
        limit=limit,
        lease_seconds=lease_seconds,
    )
