from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0011_cashier_shift"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShiftReconciliationReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")], max_length=16)),
                ("notes", models.TextField()),
                ("reviewed_at", models.DateTimeField(auto_now_add=True)),
                ("shift", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="reconciliation_review", to="transactional.cashiershift")),
                ("supervisor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shift_reviews", to="transactional.posoperator")),
            ],
        ),
    ]
