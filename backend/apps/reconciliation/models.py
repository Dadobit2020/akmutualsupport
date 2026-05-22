import uuid
import hashlib
from django.db import models
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class ImportSource(models.TextChoices):
    BANK_CSV = "bank_csv", "Bank CSV"
    TITHELY_CSV = "tithely_csv", "Tithely CSV"
    MANUAL = "manual", "Manual Entry"


class ImportBatchStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"


class MatchStatus(models.TextChoices):
    UNMATCHED = "unmatched", "Unmatched"
    AUTO_MATCHED = "auto_matched", "Auto-Matched"
    MANUALLY_MATCHED = "manually_matched", "Manually Matched"
    APPLIED = "applied", "Applied to Ledger"
    DUPLICATE = "duplicate", "Duplicate"
    REJECTED = "rejected", "Rejected / Skipped"


class ImportBatch(OrganizationScopedModel):
    """One CSV upload. Retains the original file for re-processing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, choices=ImportSource.choices)
    file = models.FileField(upload_to="reconciliation/imports/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=15, choices=ImportBatchStatus.choices, default=ImportBatchStatus.PENDING)
    uploaded_by = models.ForeignKey("identity.User", on_delete=models.PROTECT)
    row_count = models.PositiveIntegerField(default=0)
    matched_count = models.PositiveIntegerField(default=0)
    applied_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "import_batch"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source} import — {self.original_filename} ({self.created_at.date()})"


class ImportedTransaction(OrganizationScopedModel):
    """
    A single normalized row from an import batch.
    Retained forever for audit; matched to produce Payment records.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="transactions")

    # Normalized fields
    transaction_date = models.DateField()
    amount_cents = models.PositiveIntegerField()
    payer_name = models.CharField(max_length=300, blank=True)
    memo = models.CharField(max_length=500, blank=True)
    raw_description = models.CharField(max_length=500, blank=True)
    source_reference = models.CharField(max_length=200, blank=True)

    # De-duplication fingerprint
    fingerprint = models.CharField(max_length=64, db_index=True)

    # Matching results
    match_status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.UNMATCHED)
    confidence_score = models.SmallIntegerField(default=0, help_text="0–100")
    matched_member = models.ForeignKey(
        "membership.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_matches",
    )
    matched_obligation = models.ForeignKey(
        "obligations.Obligation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_matches",
    )
    match_explanation = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_transactions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "imported_transaction"
        indexes = [
            models.Index(fields=["organization", "match_status"]),
            models.Index(fields=["transaction_date"]),
            models.Index(fields=["fingerprint"]),
        ]

    def __str__(self):
        return f"{self.transaction_date} — {self.payer_name} — {self.amount_cents}¢"

    @classmethod
    def compute_fingerprint(cls, date, amount_cents: int, payer_name: str, source_reference: str) -> str:
        raw = f"{date}|{amount_cents}|{payer_name.strip().lower()}|{source_reference.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:64]
