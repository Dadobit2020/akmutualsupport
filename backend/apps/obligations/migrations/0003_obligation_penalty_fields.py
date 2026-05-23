from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("obligations", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="obligation",
            name="original_amount_cents",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="obligation",
            name="penalty_weeks_applied",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
