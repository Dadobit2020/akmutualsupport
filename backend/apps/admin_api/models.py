from django.db import models


class OrgSettings(models.Model):
    organization = models.OneToOneField(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="settings",
    )
    entrance_fee_cents = models.PositiveIntegerField(default=20000)
    maintenance_fee_cents = models.PositiveIntegerField(default=5000)
    maintenance_fee_anchor_month = models.PositiveSmallIntegerField(default=1)
    assessment_due_days = models.PositiveSmallIntegerField(default=30)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "org_settings"


class SettingsAuditLog(models.Model):
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="settings_audit_logs",
    )
    changed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settings_audit_log"
        ordering = ["-changed_at"]
