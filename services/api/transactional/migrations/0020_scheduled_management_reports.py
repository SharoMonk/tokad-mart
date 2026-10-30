from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("transactional", "0019_expense_controls")]
    operations = [
        migrations.CreateModel(
            name="ScheduledManagementReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recipient_email", models.EmailField(max_length=254)),
                ("frequency", models.CharField(choices=[("DAILY", "Daily"), ("WEEKLY", "Weekly")], max_length=8)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.posoperator")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="transactional.poslocation")),
            ],
        ),
        migrations.CreateModel(
            name="ManagementReportRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("status", models.CharField(choices=[("CLAIMED", "Claimed"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed")], default="CLAIMED", max_length=12)),
                ("detail", models.CharField(blank=True, max_length=500)),
                ("claimed_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="transactional.scheduledmanagementreport")),
            ],
        ),
        migrations.AddConstraint(
            model_name="managementreportrun",
            constraint=models.UniqueConstraint(fields=("schedule", "period_end"), name="uniq_management_report_period"),
        ),
    ]
