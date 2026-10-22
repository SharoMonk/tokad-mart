from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactional", "0006_payment_webhook_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="provider_metadata",
            field=models.JSONField(default=dict),
        ),
    ]
