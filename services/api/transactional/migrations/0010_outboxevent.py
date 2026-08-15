from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactional", "0009_posoperator_locations_posoperator_terminals_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OutboxEvent",
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
                (
                    "event_type",
                    models.CharField(max_length=128),
                ),
                (
                    "aggregate_type",
                    models.CharField(max_length=128),
                ),
                (
                    "aggregate_id",
                    models.CharField(max_length=128),
                ),
                (
                    "idempotency_key",
                    models.CharField(max_length=255, unique=True),
                ),
                (
                    "payload",
                    models.JSONField(default=dict),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
                (
                    "attempts",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "available_at",
                    models.DateTimeField(),
                ),
                (
                    "locked_until",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "processed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_error",
                    models.TextField(blank=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="outboxevent",
            index=models.Index(
                fields=["status", "available_at"],
                name="trans_outbox_status_available_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="outboxevent",
            index=models.Index(
                fields=["aggregate_type", "aggregate_id"],
                name="trans_outbox_aggregate_idx",
            ),
        ),
    ]
