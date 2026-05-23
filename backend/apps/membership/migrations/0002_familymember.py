import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("membership", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FamilyMember",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("first_name_am", models.CharField(blank=True, max_length=100)),
                ("last_name_am", models.CharField(blank=True, max_length=100)),
                ("relationship", models.CharField(
                    choices=[
                        ("spouse", "Spouse"),
                        ("child", "Child"),
                        ("parent", "Parent"),
                        ("sibling", "Sibling"),
                        ("other", "Other"),
                    ],
                    max_length=10,
                )),
                ("date_of_birth", models.DateField()),
                ("gender", models.CharField(
                    blank=True,
                    choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
                    max_length=10,
                )),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("member", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="family_members",
                    to="membership.member",
                )),
            ],
            options={"db_table": "family_member", "ordering": ["relationship", "date_of_birth"]},
        ),
    ]
