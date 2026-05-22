"""
Celery tasks for the reconciliation pipeline.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_import_batch(self, batch_id: str):
    """
    Parse, normalize, de-duplicate, and match all rows in an ImportBatch.
    Auto-applies high-confidence matches; queues the rest for human review.
    """
    from .models import ImportBatch, ImportedTransaction, ImportBatchStatus, MatchStatus
    from .parsers import parse_csv, TITHELY_COLUMN_MAP, BANK_OF_AMERICA_COLUMN_MAP
    from .matching import find_best_match
    from apps.obligations.service import apply_payment

    try:
        batch = ImportBatch.objects.select_related("organization", "uploaded_by").get(id=batch_id)
    except ImportBatch.DoesNotExist:
        logger.error(f"ImportBatch {batch_id} not found")
        return

    batch.status = ImportBatchStatus.PROCESSING
    batch.save(update_fields=["status", "updated_at"])

    try:
        content = batch.file.read()

        if batch.source == "tithely_csv":
            column_map = TITHELY_COLUMN_MAP
        else:
            column_map = BANK_OF_AMERICA_COLUMN_MAP  # default; treasurer can override

        parsed_rows = parse_csv(content, **column_map)

        auto_apply_threshold = settings.RECONCILIATION_AUTO_APPLY_THRESHOLD
        review_threshold = settings.RECONCILIATION_REVIEW_THRESHOLD

        row_count = 0
        matched_count = 0
        applied_count = 0

        for parsed_row in parsed_rows:
            row_count += 1

            # De-duplication
            fingerprint = ImportedTransaction.compute_fingerprint(
                parsed_row.transaction_date,
                parsed_row.amount_cents,
                parsed_row.payer_name,
                parsed_row.source_reference,
            )
            if ImportedTransaction.objects.filter(
                organization=batch.organization, fingerprint=fingerprint
            ).exists():
                # Create the row but mark as duplicate
                ImportedTransaction.objects.create(
                    organization=batch.organization,
                    batch=batch,
                    transaction_date=parsed_row.transaction_date,
                    amount_cents=parsed_row.amount_cents,
                    payer_name=parsed_row.payer_name,
                    memo=parsed_row.memo,
                    raw_description=parsed_row.raw_description,
                    source_reference=parsed_row.source_reference,
                    fingerprint=fingerprint,
                    match_status=MatchStatus.DUPLICATE,
                )
                continue

            # Matching
            best_match = find_best_match(
                organization=batch.organization,
                payer_name=parsed_row.payer_name,
                amount_cents=parsed_row.amount_cents,
                memo=parsed_row.memo,
                transaction_date=parsed_row.transaction_date,
                auto_apply_threshold=auto_apply_threshold,
                review_threshold=review_threshold,
            )

            if best_match is None:
                status = MatchStatus.UNMATCHED
                score = 0
                member = None
                obligation = None
                explanation = "No match found above threshold"
            else:
                matched_count += 1
                status = MatchStatus.AUTO_MATCHED if best_match.score >= auto_apply_threshold else MatchStatus.UNMATCHED
                score = best_match.score
                member = best_match.member
                obligation = best_match.matched_obligation
                explanation = best_match.explanation_text

            imported_txn = ImportedTransaction.objects.create(
                organization=batch.organization,
                batch=batch,
                transaction_date=parsed_row.transaction_date,
                amount_cents=parsed_row.amount_cents,
                payer_name=parsed_row.payer_name,
                memo=parsed_row.memo,
                raw_description=parsed_row.raw_description,
                source_reference=parsed_row.source_reference,
                fingerprint=fingerprint,
                match_status=status,
                confidence_score=score,
                matched_member=member,
                matched_obligation=obligation,
                match_explanation=explanation,
            )

            # Auto-apply high-confidence matches
            if status == MatchStatus.AUTO_MATCHED and member:
                try:
                    apply_payment(
                        organization=batch.organization,
                        member=member,
                        amount_cents=parsed_row.amount_cents,
                        payment_date=parsed_row.transaction_date,
                        method="bank_transfer",
                        reference=parsed_row.source_reference,
                        posted_by=batch.uploaded_by,
                        imported_transaction=imported_txn,
                    )
                    imported_txn.match_status = MatchStatus.APPLIED
                    imported_txn.save(update_fields=["match_status", "updated_at"])
                    applied_count += 1
                except Exception as e:
                    logger.error(f"Auto-apply failed for ImportedTransaction {imported_txn.id}: {e}")
                    imported_txn.match_status = MatchStatus.UNMATCHED
                    imported_txn.match_explanation += f" [Auto-apply failed: {e}]"
                    imported_txn.save(update_fields=["match_status", "match_explanation", "updated_at"])

        batch.row_count = row_count
        batch.matched_count = matched_count
        batch.applied_count = applied_count
        batch.status = ImportBatchStatus.COMPLETE
        batch.save(update_fields=["row_count", "matched_count", "applied_count", "status", "updated_at"])

    except Exception as exc:
        logger.exception(f"ImportBatch {batch_id} failed: {exc}")
        batch.status = ImportBatchStatus.FAILED
        batch.error_message = str(exc)
        batch.save(update_fields=["status", "error_message", "updated_at"])
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
