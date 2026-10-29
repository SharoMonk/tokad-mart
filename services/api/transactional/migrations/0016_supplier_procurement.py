from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("transactional", "0015_stock_operation")]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("contact", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=64, unique=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="transactional.supplier")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="transactional.poslocation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseOrderLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_ordered", models.PositiveIntegerField()),
                ("quantity_received", models.PositiveIntegerField(default=0)),
                ("unit_cost_minor", models.PositiveBigIntegerField()),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="transactional.purchaseorder")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.product")),
            ],
        ),
        migrations.AddConstraint(
            model_name="purchaseorderline",
            constraint=models.UniqueConstraint(fields=("order", "product"), name="uniq_po_order_product"),
        ),
        migrations.CreateModel(
            name="GoodsReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=128)),
                ("key", models.CharField(max_length=128, unique=True)),
                ("request_fingerprint", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="transactional.purchaseorder")),
                ("received_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
            ],
        ),
        migrations.AddConstraint(
            model_name="goodsreceipt",
            constraint=models.UniqueConstraint(fields=("order", "reference"), name="uniq_po_receipt_ref"),
        ),
        migrations.CreateModel(
            name="GoodsReceiptLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("receipt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="transactional.goodsreceipt")),
                ("order_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.purchaseorderline")),
                ("movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="transactional.inventorymovement")),
            ],
        ),
        migrations.AddConstraint(
            model_name="goodsreceiptline",
            constraint=models.UniqueConstraint(fields=("receipt", "order_line"), name="uniq_goods_receipt_line"),
        ),
    ]
