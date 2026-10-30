"""Execute scheduled store reports; invoke once daily via cron/systemd."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from transactional.report_scheduling import execute_due_reports


class Command(BaseCommand):
    help = "Execute due scheduled reports (email backend must be explicitly enabled)."

    def handle(self, *args, **options):
        runs = execute_due_reports(on=timezone.localdate())
        for run in runs:
            self.stdout.write(
                f"schedule={run.schedule_id} period={run.period_end} status={run.status}"
            )
        self.stdout.write(f"attempted={len(runs)}")
