from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("transactional", "0018_supplier_payment_evidence")]

    operations = [
        migrations.CreateModel(
            name="StoreExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=128, unique=True)),
                ("category", models.CharField(max_length=64)),
                ("description", models.CharField(max_length=500)),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("incurred_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="transactional.poslocation")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
            ],
        ),
        migrations.CreateModel(
            name="ExpenseReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")], max_length=12)),
                ("notes", models.CharField(max_length=1000)),
                ("reviewed_at", models.DateTimeField(auto_now_add=True)),
                ("expense", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="review", to="transactional.storeexpense")),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
            ],
        ),
    ]
