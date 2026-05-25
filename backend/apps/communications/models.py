import uuid
from django.db import models
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class CommunicationChannel(models.TextChoices):
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class CommunicationStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"


class MessageTemplate(OrganizationScopedModel):
    """Versioned notification templates with variable substitution."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    channel = models.CharField(max_length=10, choices=CommunicationChannel.choices)
    subject = models.CharField(max_length=300, blank=True)
    body_en = models.TextField()
    body_am = models.TextField(blank=True, help_text="Amharic translation (Phase 2)")
    category = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "message_template"
        unique_together = [("organization", "name")]

    def __str__(self):
        return f"{self.name} ({self.channel})"

    def render(self, context: dict, language: str = "en") -> tuple[str, str]:
        """Return (subject, body) with context variables substituted."""
        body = self.body_am if language == "am" and self.body_am else self.body_en
        subject = self.subject
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            body = body.replace(placeholder, str(value))
            subject = subject.replace(placeholder, str(value))
        return subject, body


class Communication(OrganizationScopedModel):
    """A queued or sent message. Append-only; status updated in place."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_member = models.ForeignKey(
        "membership.Member",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="communications",
    )
    channel = models.CharField(max_length=10, choices=CommunicationChannel.choices)
    recipient_address = models.CharField(max_length=300)
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=12, choices=CommunicationStatus.choices, default=CommunicationStatus.QUEUED)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    # Contextual link
    obligation = models.ForeignKey(
        "obligations.Obligation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        "obligations.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "communication"
        indexes = [models.Index(fields=["status", "channel"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} to {self.recipient_address} ({self.status})"
