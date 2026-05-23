from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrgSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entrance_fee_cents", models.PositiveIntegerField(default=20000)),
                ("maintenance_fee_cents", models.PositiveIntegerField(default=5000)),
                ("maintenance_fee_anchor_month", models.PositiveSmallIntegerField(default=1)),
                ("assessment_due_days", models.PositiveSmallIntegerField(default=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="settings",
                    to="identity.organization",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "org_settings"},
        ),
        migrations.CreateModel(
            name="SettingsAuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("field_name", models.CharField(max_length=100)),
                ("old_value", models.TextField()),
                ("new_value", models.TextField()),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="settings_audit_logs",
                    to="identity.organization",
                )),
            ],
            options={"db_table": "settings_audit_log", "ordering": ["-changed_at"]},
        ),
    ]
