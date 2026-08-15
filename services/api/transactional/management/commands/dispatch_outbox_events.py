from django.core.management.base import BaseCommand

from transactional.outbox_dispatcher import dispatch_outbox_events


class Command(BaseCommand):
    help = "Dispatch pending transactional outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--lease-seconds", type=int, default=60)

    def handle(self, *args, **options):
        result = dispatch_outbox_events(
            {},
            limit=options["limit"],
            lease_seconds=options["lease_seconds"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"completed={result.completed} failed={result.failed} skipped={result.skipped}"
            )
        )
