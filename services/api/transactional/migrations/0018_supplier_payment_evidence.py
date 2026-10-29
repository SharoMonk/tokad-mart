from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("transactional", "0017_procurement_approval_invoice")]

    operations = [
        migrations.CreateModel(
            name="SupplierPaymentEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=128, unique=True)),
                ("idempotency_key", models.CharField(max_length=128, unique=True)),
                ("fingerprint", models.CharField(max_length=64)),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("notes", models.CharField(max_length=1000)),
                ("status", models.CharField(choices=[("RECORDED", "Recorded"), ("VERIFIED", "Manually verified")], default="RECORDED", max_length=12)),
                ("verification_notes", models.CharField(blank=True, max_length=1000)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_evidence", to="transactional.supplierinvoice")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_payments_recorded", to="transactional.posoperator")),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_payments_verified", to="transactional.posoperator")),
            ],
        ),
    ]
