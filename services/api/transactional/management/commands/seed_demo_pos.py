"""Create a repeatable, development-only POS operator and sample catalog.

This command never resets stock, sale records, payments, or existing passwords.
Do not use this command to onboard production employees or inventory.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product,
)


DEMO_PRODUCTS = (
    ("DEMO-RICE-001", "Demo Rice 1kg", 350000, 20),
    ("DEMO-SUGAR-001", "Demo Sugar 1kg", 220000, 30),
    ("DEMO-SOAP-001", "Demo Bath Soap", 85000, 40),
    ("DEMO-MILK-001", "Demo Powdered Milk", 175000, 25),
)


class Command(BaseCommand):
    help = "Seed development-only POS location, terminal, cashier and demonstration stock."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo_cashier")
        parser.add_argument("--location-code", default="MAIN")
        parser.add_argument("--terminal-code", default="MAIN-01")
        parser.add_argument(
            "--confirm-demo", action="store_true",
            help="Explicitly acknowledge that demo catalog and stock will be inserted.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo POS setup is disabled unless DEBUG=True.")
        if not options["confirm_demo"]:
            raise CommandError("Pass --confirm-demo to explicitly authorize demo data.")
        username = options["username"].strip()
        location_code = options["location_code"].strip()
        terminal_code = options["terminal_code"].strip()
        if not all((username, location_code, terminal_code)):
            raise CommandError("Username, location code and terminal code must be nonempty.")

        location, _ = POSLocation.objects.get_or_create(
            code=location_code, defaults={"name": "Demo Main Store"}
        )
        if not location.is_active:
            raise CommandError("The selected location is inactive.")
        terminal, _ = POSTerminal.objects.get_or_create(
            location=location, code=terminal_code,
            defaults={"name": "Demo POS Terminal"}
        )
        if not terminal.is_active:
            raise CommandError("The selected terminal is inactive.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": True, "is_active": True},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        elif not user.is_active or not user.is_staff:
            raise CommandError(
                "Existing cashier account must be active and staff-enabled; "
                "this command will not silently elevate privileges."
            )

        operator, _ = POSOperator.objects.get_or_create(user=user)
        if not operator.is_active:
            raise CommandError("Existing POS operator is inactive.")
        POSOperatorLocation.objects.get_or_create(operator=operator, location=location)
        POSOperatorTerminal.objects.get_or_create(operator=operator, terminal=terminal)

        added = 0
        for sku, name, unit_price_minor, initial_stock in DEMO_PRODUCTS:
            product, product_created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name, "currency": "NGN",
                    "unit_price_minor": unit_price_minor,
                    "is_active": True,
                },
            )
            if not product_created and (
                product.name != name or product.currency != "NGN"
                or product.unit_price_minor != unit_price_minor
            ):
                raise CommandError(
                    f"Existing SKU {sku} differs from the demo catalog. "
                    "No prices or inventory were overwritten."
                )
            _stock, stock_created = InventoryItem.objects.get_or_create(
                product=product, location_code=location_code,
                defaults={"quantity": initial_stock},
            )
            if stock_created:
                added += 1

        self.stdout.write(self.style.SUCCESS(
            f"Demo POS ready: user={username} location={location_code} "
            f"terminal={terminal_code}; new_stock_records={added}. "
            "Existing stock and passwords were preserved."
        ))
        if created or not user.has_usable_password():
            self.stdout.write(
                f"Set a cashier password with: python manage.py changepassword {username}"
            )
