from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventorymovement",
            name="reason",
            field=models.CharField(
                choices=[
                    ("SALE", "SALE"),
                    ("RETURN", "RETURN"),
                    ("PURCHASE", "PURCHASE"),
                    ("ADJUSTMENT", "ADJUSTMENT"),
                    ("TRANSFER_IN", "TRANSFER_IN"),
                    ("TRANSFER_OUT", "TRANSFER_OUT"),
                    ("DAMAGE", "DAMAGE"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "PENDING"),
                    ("SUCCEEDED", "SUCCEEDED"),
                    ("FAILED", "FAILED"),
                    ("CANCELLED", "CANCELLED"),
                    ("REFUNDED", "REFUNDED"),
                ],
                default="PENDING",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="sale",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "DRAFT"),
                    ("PENDING_PAYMENT", "PENDING_PAYMENT"),
                    ("COMPLETED", "COMPLETED"),
                    ("PAYMENT_FAILED", "PAYMENT_FAILED"),
                    ("CANCELLED", "CANCELLED"),
                ],
                default="DRAFT",
                max_length=32,
            ),
        ),
    ]
