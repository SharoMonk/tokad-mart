from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("transactional", "0005_pos_access_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentWebhookEvent",
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
                ("event_id", models.CharField(max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="webhook_events",
                        to="transactional.payment",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="paymentwebhookevent",
            constraint=models.UniqueConstraint(
                fields=("provider", "event_id"),
                name="uniq_payment_webhook_provider_event",
            ),
        ),
    ]
