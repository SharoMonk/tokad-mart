from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("transactional", "0004_payment_pos_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="POSLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="POSTerminal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="terminals", to="transactional.poslocation")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("location", "code"), name="uniq_pos_terminal_location_code"),
                ],
            },
        ),
        migrations.CreateModel(
            name="POSOperator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("OPERATOR", "Operator"), ("SUPERVISOR", "Supervisor")], default="OPERATOR", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="pos_operator", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="POSOperatorLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operator_assignments", to="transactional.poslocation")),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="location_assignments", to="transactional.posoperator")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("operator", "location"), name="uniq_pos_operator_location"),
                ],
            },
        ),
        migrations.CreateModel(
            name="POSOperatorTerminal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="terminal_assignments", to="transactional.posoperator")),
                ("terminal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operator_assignments", to="transactional.posterminal")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("operator", "terminal"), name="uniq_pos_operator_terminal"),
                ],
            },
        ),
    ]
