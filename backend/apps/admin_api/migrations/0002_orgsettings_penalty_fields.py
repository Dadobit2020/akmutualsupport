from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="orgsettings",
            name="late_penalty_pct",
            field=models.PositiveSmallIntegerField(default=15),
        ),
        migrations.AddField(
            model_name="orgsettings",
            name="suspension_after_days",
            field=models.PositiveSmallIntegerField(default=90),
        ),
    ]
