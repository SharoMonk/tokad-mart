"""Bind a physical manufacturer barcode to an existing canonical product."""
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from transactional.models import Product, ProductBarcode


class Command(BaseCommand):
    help = "Link a physical barcode to an existing SKU without altering the sales ledger."

    def add_arguments(self, parser):
        parser.add_argument("--sku", required=True)
        parser.add_argument("--barcode", required=True)

    def handle(self, *args, **options):
        sku = options["sku"]
        barcode = options["barcode"]
        if not barcode or barcode.strip() != barcode or len(barcode) > 64:
            raise CommandError("barcode must be 1-64 characters without surrounding whitespace")
        if any(ord(character) < 33 or ord(character) > 126 for character in barcode):
            raise CommandError("barcode must contain printable ASCII characters without spaces")
        try:
            with transaction.atomic():
                product = Product.objects.get(sku=sku)
                conflicting_sku = Product.objects.filter(sku=barcode).exclude(
                    pk=product.pk
                ).exists()
                if conflicting_sku:
                    raise CommandError("barcode conflicts with a different product SKU")
                existing = ProductBarcode.objects.select_for_update().filter(
                    code=barcode
                ).first()
                if existing and existing.product_id != product.pk:
                    raise CommandError("barcode is already assigned to a different product")
                if existing is None:
                    ProductBarcode.objects.create(product=product, code=barcode)
        except Product.DoesNotExist as exc:
            raise CommandError("product SKU does not exist") from exc
        except IntegrityError as exc:
            raise CommandError("barcode was concurrently assigned; inspect mappings") from exc
        self.stdout.write(self.style.SUCCESS(
            f"barcode {barcode} linked to SKU {sku}"
        ))
