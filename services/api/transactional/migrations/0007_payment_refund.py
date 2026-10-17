from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0006_payment_webhook_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentRefund",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(max_length=64)),
                ("provider_reference", models.CharField(max_length=255)),
                ("provider_refund_reference", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("idempotency_key", models.CharField(max_length=255, unique=True)),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("currency", models.CharField(max_length=3)),
                ("status", models.CharField(choices=[("REQUESTED", "REQUESTED"), ("SUCCEEDED", "SUCCEEDED"), ("FAILED", "FAILED")], default="REQUESTED", max_length=32)),
                ("provider_metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="transactional.payment")),
            ],
        ),
    ]
