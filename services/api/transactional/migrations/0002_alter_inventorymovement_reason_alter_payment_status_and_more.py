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
                    ("SALE", "Sale"),
                    ("RETURN", "Return"),
                    ("PURCHASE", "Purchase"),
                    ("ADJUSTMENT", "Adjustment"),
                    ("TRANSFER_IN", "Transfer in"),
                    ("TRANSFER_OUT", "Transfer out"),
                    ("DAMAGE", "Damage"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("SUCCEEDED", "Succeeded"),
                    ("FAILED", "Failed"),
                    ("CANCELLED", "Cancelled"),
                    ("REFUNDED", "Refunded"),
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
                    ("DRAFT", "Draft"),
                    ("PENDING_PAYMENT", "Pending payment"),
                    ("COMPLETED", "Completed"),
                    ("PAYMENT_FAILED", "Payment failed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="DRAFT",
                max_length=32,
            ),
        ),
    ]
