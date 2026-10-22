from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0012_shift_reconciliation_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductBarcode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="barcodes", to="transactional.product")),
            ],
        ),
    ]
