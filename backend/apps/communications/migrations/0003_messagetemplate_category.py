from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagetemplate",
            name="category",
            field=models.CharField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="messagetemplate",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterUniqueTogether(
            name="messagetemplate",
            unique_together={("organization", "name")},
        ),
    ]
