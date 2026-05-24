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
    # Late penalty policy
    late_penalty_pct = models.PositiveSmallIntegerField(default=15)
    suspension_after_days = models.PositiveSmallIntegerField(default=90)
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


class AdminActionLog(models.Model):
    """Immutable record of every significant admin action."""

    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="admin_action_logs",
    )
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_actions",
    )
    action = models.CharField(max_length=60)        # e.g. "payment_recorded"
    target_type = models.CharField(max_length=50, blank=True)  # "Member", "Payment", …
    target_id = models.CharField(max_length=100, blank=True)
    target_label = models.CharField(max_length=255, blank=True)  # human-readable name
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_action_log"
        ordering = ["-created_at"]
