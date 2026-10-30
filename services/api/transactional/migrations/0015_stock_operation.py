from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0014_rename_trans_outbox_status_available_idx_transaction_status_c5bc91_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StockOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=128, unique=True)),
                ("request_fingerprint", models.CharField(max_length=64)),
                ("quantity_after", models.BigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="stock_operation", to="transactional.inventorymovement")),
            ],
        ),
    ]
