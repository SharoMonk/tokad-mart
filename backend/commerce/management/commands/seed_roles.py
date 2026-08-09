from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Create the default Tokad Mart role groups."

    def handle(self, *args, **options):
        for name in ("Cashier", "Manager", "Owner"):
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Tokad Mart roles are ready."))
