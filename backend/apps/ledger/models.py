"""
Double-entry ledger — the financial core.

Design rules enforced here:
  - LedgerEntry rows are NEVER updated or deleted. Mutations on posted entries
    are a programming error and should raise immediately.
  - Every LedgerTransaction must balance: sum of debit entries == sum of credit entries.
  - All amounts are positive integers in the smallest currency unit (cents).
  - Corrections are posted as new reversing transactions, leaving the original visible.
"""
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class AccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity"
    REVENUE = "revenue", "Revenue"
    EXPENSE = "expense", "Expense"


class LedgerAccount(OrganizationScopedModel):
    """
    Chart of accounts. Small and mostly fixed.
    Standard accounts are seeded in a data migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, help_text="Short code, e.g. CASH, RECV, PAYOUT")
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=12, choices=AccountType.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "ledger_account"
        unique_together = [("organization", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"[{self.code}] {self.name}"


class TransactionSource(models.TextChoices):
    MANUAL = "manual", "Manual Entry"
    EVENT_OBLIGATION = "event_obligation", "Event Obligation"
    PAYMENT = "payment", "Payment"
    REVERSAL = "reversal", "Reversal"
    DUES = "dues", "Recurring Dues"
    PAYOUT = "payout", "Event Payout"
    WAIVER = "waiver", "Obligation Waiver"
    ADJUSTMENT = "adjustment", "Adjustment"


class LedgerTransaction(OrganizationScopedModel):
    """
    A balanced group of ledger entries. Every transaction must net to zero.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=500)
    transaction_date = models.DateField(db_index=True)
    source = models.CharField(max_length=20, choices=TransactionSource.choices)
    posted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="posted_transactions",
    )
    # Optional links to source objects
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_transactions",
    )
    # Reversal link: if this transaction reverses another, record it
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "ledger_transaction"
        indexes = [
            models.Index(fields=["organization", "transaction_date"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"{self.transaction_date} | {self.description}"

    def validate_balanced(self):
        """Raises ValidationError if this transaction does not balance."""
        entries = self.entries.all()
        total_debits = sum(e.debit_cents for e in entries)
        total_credits = sum(e.credit_cents for e in entries)
        if total_debits != total_credits:
            raise ValidationError(
                f"Transaction {self.id} does not balance: "
                f"debits={total_debits}, credits={total_credits}"
            )


class LedgerEntry(TimeStampedModel):
    """
    A single line in a transaction. IMMUTABLE after creation.

    The combination of debit_cents and credit_cents:
      - Exactly one is positive; the other must be 0.
      - Both are non-negative integers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ledger_transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    debit_cents = models.PositiveIntegerField(default=0)
    credit_cents = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=300, blank=True)

    # Optional contextual links
    member = models.ForeignKey(
        "membership.Member",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    obligation = models.ForeignKey(
        "obligations.Obligation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    class Meta:
        db_table = "ledger_entry"
        indexes = [
            models.Index(fields=["account", "ledger_transaction"]),
            models.Index(fields=["member"]),
        ]

    def __str__(self):
        if self.debit_cents:
            return f"DR {self.debit_cents}¢ → {self.account}"
        return f"CR {self.credit_cents}¢ → {self.account}"

    def clean(self):
        if self.debit_cents == 0 and self.credit_cents == 0:
            raise ValidationError("An entry must have a non-zero debit or credit.")
        if self.debit_cents > 0 and self.credit_cents > 0:
            raise ValidationError("An entry cannot have both debit and credit amounts.")

    def save(self, *args, **kwargs):
        self.clean()
        if not self._state.adding:
            # Prevent mutation of posted entries — only new records may be saved
            raise ValidationError("LedgerEntry records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("LedgerEntry records cannot be deleted. Post a reversing transaction instead.")
