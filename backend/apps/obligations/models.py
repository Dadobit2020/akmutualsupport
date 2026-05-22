import uuid
from django.db import models
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class ObligationStatus(models.TextChoices):
    OPEN = "open", "Open"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    WAIVED = "waived", "Waived"
    WRITTEN_OFF = "written_off", "Written Off"
    CANCELLED = "cancelled", "Cancelled"


class ObligationType(models.TextChoices):
    EVENT = "event", "Event"
    DUES = "dues", "Recurring Dues"


class Obligation(OrganizationScopedModel):
    """
    What a member owes for a specific event or recurring dues period.
    Payment is tracked via the ledger; the paid_cents field is derived (cached) for performance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation_type = models.CharField(max_length=10, choices=ObligationType.choices, default=ObligationType.EVENT)
    member = models.ForeignKey(
        "membership.Member",
        on_delete=models.PROTECT,
        related_name="obligations",
        db_index=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="obligations",
    )
    amount_cents = models.PositiveIntegerField()
    # Cached paid amount — derived from ledger entries but kept here for fast queries
    paid_cents = models.PositiveIntegerField(default=0)
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=15, choices=ObligationStatus.choices, default=ObligationStatus.OPEN, db_index=True)
    waiver_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "obligation"
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["member", "status"]),
            models.Index(fields=["due_date"]),
        ]
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.member} — {self.obligation_type} — {self.amount_cents}¢ ({self.status})"

    @property
    def outstanding_cents(self):
        return max(0, self.amount_cents - self.paid_cents)

    def apply_payment_cents(self, amount: int):
        """
        Apply a payment amount to this obligation. Updates paid_cents and status.
        The caller is responsible for posting the corresponding ledger entries.
        """
        if self.status in (ObligationStatus.WAIVED, ObligationStatus.CANCELLED, ObligationStatus.WRITTEN_OFF):
            raise ValueError(f"Cannot apply payment to obligation with status '{self.status}'.")
        self.paid_cents = min(self.amount_cents, self.paid_cents + amount)
        if self.paid_cents >= self.amount_cents:
            self.status = ObligationStatus.PAID
        elif self.paid_cents > 0:
            self.status = ObligationStatus.PARTIALLY_PAID
        self.save(update_fields=["paid_cents", "status", "updated_at"])


class Payment(OrganizationScopedModel):
    """
    A recorded inbound payment. May apply to one or more obligations.
    Created either by the reconciliation engine (from an imported transaction)
    or manually by an admin.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        "membership.Member",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    amount_cents = models.PositiveIntegerField()
    payment_date = models.DateField(db_index=True)
    method = models.CharField(
        max_length=30,
        choices=[
            ("check", "Check"),
            ("bank_transfer", "Bank Transfer"),
            ("cash", "Cash"),
            ("online", "Online (Tithely/Stripe)"),
            ("other", "Other"),
        ],
    )
    reference = models.CharField(max_length=200, blank=True, help_text="Check number, transaction ID, etc.")
    notes = models.TextField(blank=True)
    # Link back to the import row that created this (if from reconciliation)
    imported_transaction = models.OneToOneField(
        "reconciliation.ImportedTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment",
    )
    # Ledger transaction that recorded this payment
    ledger_transaction = models.OneToOneField(
        "ledger.LedgerTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment",
    )

    class Meta:
        db_table = "payment"
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Payment {self.amount_cents}¢ from {self.member} on {self.payment_date}"


class PaymentApplication(TimeStampedModel):
    """Maps a Payment to one or more Obligations (for partial payments spanning multiple obligations)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="applications")
    obligation = models.ForeignKey(Obligation, on_delete=models.PROTECT, related_name="payment_applications")
    applied_cents = models.PositiveIntegerField()

    class Meta:
        db_table = "payment_application"
