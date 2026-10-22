from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactional", "0003_alter_inventorymovement_reason_alter_sale_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="idempotency_key",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="method",
            field=models.CharField(
                choices=[
                    ("CASH", "Cash"),
                    ("CARD", "Card"),
                    ("BANK_TRANSFER", "Bank Transfer"),
                    ("MOBILE_MONEY", "Mobile Money"),
                    ("EXTERNAL", "External"),
                ],
                max_length=32,
            ),
        ),
    ]
