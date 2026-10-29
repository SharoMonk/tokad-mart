from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("transactional", "0016_supplier_procurement")]

    operations = [
        migrations.CreateModel(
            name="PurchaseOrderApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.CharField(max_length=500)),
                ("approved_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="approval", to="transactional.purchaseorder")),
            ],
        ),
        migrations.CreateModel(
            name="SupplierInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(max_length=128)),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("expected_minor", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("MATCHED", "Matched"), ("EXCEPTION", "Exception")], max_length=12)),
                ("notes", models.CharField(max_length=1000)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="transactional.supplier")),
                ("receipt", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_invoice", to="transactional.goodsreceipt")),
            ],
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.UniqueConstraint(fields=("supplier", "number"), name="uniq_supplier_invoice_number"),
        ),
    ]
