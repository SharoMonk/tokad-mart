import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transactional", "0010_outboxevent")]

    operations = [
        migrations.CreateModel(
            name="CashierShift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("CLOSED", "Closed")], default="OPEN", max_length=8)),
                ("opening_cash_minor", models.PositiveBigIntegerField(default=0)),
                ("closing_cash_minor", models.PositiveBigIntegerField(blank=True, null=True)),
                ("expected_cash_minor", models.PositiveBigIntegerField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.poslocation")),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cashier_shifts", to="transactional.posoperator")),
                ("terminal", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posterminal")),
            ],
        ),
        migrations.AddField(
            model_name="sale",
            name="shift",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales", to="transactional.cashiershift"),
        ),
        migrations.AddConstraint(
            model_name="cashiershift",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="OPEN"),
                fields=("terminal",),
                name="uniq_open_cashier_shift_per_terminal",
            ),
        ),
    ]
