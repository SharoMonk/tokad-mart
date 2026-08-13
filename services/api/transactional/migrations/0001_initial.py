from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=255, unique=True)),
                ("request_fingerprint", models.CharField(max_length=128)),
                ("response_payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("currency", models.CharField(default="NGN", max_length=3)),
                ("unit_price_minor", models.PositiveBigIntegerField()),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor", models.CharField(max_length=255)),
                ("action", models.CharField(max_length=128)),
                ("entity_type", models.CharField(max_length=128)),
                ("entity_reference", models.CharField(max_length=255)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("location_code", models.CharField(max_length=64)),
                ("quantity", models.BigIntegerField(default=0)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_items", to="transactional.product")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("product", "location_code"), name="uniq_inventory_product_location"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Sale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(unique=True)),
                ("location_code", models.CharField(max_length=64)),
                ("currency", models.CharField(max_length=3)),
                ("subtotal_minor", models.PositiveBigIntegerField(default=0)),
                ("total_minor", models.PositiveBigIntegerField(default=0)),
                ("status", models.CharField(choices=[("DRAFT", "DRAFT"), ("PENDING_PAYMENT", "PENDING_PAYMENT"), ("COMPLETED", "COMPLETED"), ("PAYMENT_FAILED", "PAYMENT_FAILED"), ("CANCELLED", "CANCELLED")], default="DRAFT", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="transactional.customer")),
            ],
        ),
        migrations.CreateModel(
            name="SaleLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("name_snapshot", models.CharField(max_length=255)),
                ("quantity", models.PositiveBigIntegerField()),
                ("unit_price_minor", models.PositiveBigIntegerField()),
                ("line_total_minor", models.PositiveBigIntegerField()),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.product")),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="transactional.sale")),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=64)),
                ("provider_reference", models.CharField(max_length=255, unique=True)),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("currency", models.CharField(max_length=3)),
                ("status", models.CharField(choices=[("PENDING", "PENDING"), ("SUCCEEDED", "SUCCEEDED"), ("FAILED", "FAILED"), ("CANCELLED", "CANCELLED"), ("REFUNDED", "REFUNDED")], default="PENDING", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="transactional.sale")),
            ],
        ),
        migrations.CreateModel(
            name="InventoryMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_delta", models.BigIntegerField()),
                ("reason", models.CharField(choices=[("SALE", "SALE"), ("RETURN", "RETURN"), ("PURCHASE", "PURCHASE"), ("ADJUSTMENT", "ADJUSTMENT"), ("TRANSFER_IN", "TRANSFER_IN"), ("TRANSFER_OUT", "TRANSFER_OUT"), ("DAMAGE", "DAMAGE")], max_length=32)),
                ("reference", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("inventory_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="transactional.inventoryitem")),
            ],
        ),
    ]
