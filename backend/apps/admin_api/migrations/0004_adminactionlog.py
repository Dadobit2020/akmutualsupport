from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("admin_api", "0003_alter_orgsettings_id_alter_settingsauditlog_id"),
        ("identity", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=60)),
                ("target_type", models.CharField(blank=True, max_length=50)),
                ("target_id", models.CharField(blank=True, max_length=100)),
                ("target_label", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="admin_actions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="admin_action_logs",
                    to="identity.organization",
                )),
            ],
            options={"db_table": "admin_action_log", "ordering": ["-created_at"]},
        ),
    ]
