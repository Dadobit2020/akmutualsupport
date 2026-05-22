import uuid
from django.db import models
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class EventType(models.TextChoices):
    BEREAVEMENT = "bereavement", "Bereavement"
    MEDICAL_EMERGENCY = "medical_emergency", "Medical Emergency"
    OTHER = "other", "Other"


class EventStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    OBLIGATIONS_GENERATED = "obligations_generated", "Obligations Generated"
    COLLECTING = "collecting", "Collecting"
    CLOSED = "closed", "Closed"
    REVERSED = "reversed", "Reversed"


TERMINAL_STATUSES = {EventStatus.REVERSED, EventStatus.CLOSED, EventStatus.REJECTED}
APPROVAL_REQUIRED_STATUSES = {EventStatus.DRAFT, EventStatus.PENDING_APPROVAL}


class Event(OrganizationScopedModel):
    """
    A bereavement or emergency event. Approved events trigger obligation generation.
    Reversed events are corrected by posting compensating ledger entries, not by deletion.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    affected_household = models.ForeignKey(
        "membership.Household",
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_date = models.DateField()
    description = models.TextField()
    payout_amount_cents = models.PositiveIntegerField(
        help_text="Total payout to the affected household, in cents.",
    )
    status = models.CharField(
        max_length=25,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
        db_index=True,
    )
    # Approval
    submitted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_events",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_events",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    # Contribution deadline (set on approval)
    contribution_deadline = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "event"
        ordering = ["-event_date"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["event_date"]),
        ]

    def __str__(self):
        return f"{self.event_type} — {self.affected_household} ({self.event_date})"

    @property
    def is_editable(self):
        return self.status in (EventStatus.DRAFT,)

    @property
    def is_reversible(self):
        return self.status not in TERMINAL_STATUSES and self.status != EventStatus.DRAFT


class EventOverride(TimeStampedModel):
    """
    Chairperson-only emergency override on an event. Fully audit-logged.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="overrides")
    applied_by = models.ForeignKey("identity.User", on_delete=models.PROTECT)
    reason = models.TextField()
    action = models.CharField(max_length=100)

    class Meta:
        db_table = "event_override"
