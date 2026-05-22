"""
Obligation & payment service.

apply_payment() is the single path through which a confirmed payment is
converted into ledger entries and obligation updates.
"""
import datetime
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from .models import Obligation, ObligationStatus, Payment, PaymentApplication
from apps.ledger.service import post_transaction
from apps.ledger.models import TransactionSource


def apply_payment(
    *,
    organization,
    member,
    amount_cents: int,
    payment_date: datetime.date,
    method: str,
    reference: str = "",
    posted_by,
    imported_transaction=None,
    notes: str = "",
) -> Payment:
    """
    Apply a confirmed payment to a member's open obligations (oldest-first).
    Creates:
      - A Payment record
      - PaymentApplication records for each obligation touched
      - A balanced LedgerTransaction (DR Cash, CR Member Receivables)
    """
    if amount_cents <= 0:
        raise ValidationError("Payment amount must be positive.")

    open_obligations = list(
        Obligation.objects.filter(
            organization=organization,
            member=member,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        ).order_by("due_date")
    )

    with db_transaction.atomic():
        ledger_txn = post_transaction(
            organization=organization,
            description=f"Payment from {member.get_full_name()} — {amount_cents}¢",
            transaction_date=payment_date,
            source=TransactionSource.PAYMENT,
            posted_by=posted_by,
            entries=[
                {
                    "account_code": "CASH",
                    "debit_cents": amount_cents,
                    "credit_cents": 0,
                    "description": f"Cash received from {member.get_full_name()}",
                    "member": member,
                },
                {
                    "account_code": "RECV",
                    "debit_cents": 0,
                    "credit_cents": amount_cents,
                    "description": f"Clear receivable for {member.get_full_name()}",
                    "member": member,
                },
            ],
        )

        payment = Payment.objects.create(
            organization=organization,
            member=member,
            amount_cents=amount_cents,
            payment_date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
            imported_transaction=imported_transaction,
            ledger_transaction=ledger_txn,
        )

        remaining = amount_cents
        for obligation in open_obligations:
            if remaining <= 0:
                break
            to_apply = min(remaining, obligation.outstanding_cents)
            if to_apply <= 0:
                continue
            PaymentApplication.objects.create(
                payment=payment,
                obligation=obligation,
                applied_cents=to_apply,
            )
            obligation.apply_payment_cents(to_apply)
            remaining -= to_apply

        # Overpayment: remaining > 0 — stays as a credit balance on the ledger (already posted)

    return payment


def waive_obligation(obligation: Obligation, waived_by, reason: str) -> Obligation:
    if obligation.status not in (ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID):
        raise ValidationError("Only open or partially paid obligations can be waived.")
    if not reason.strip():
        raise ValidationError("A reason is required for waivers.")

    remaining = obligation.outstanding_cents
    if remaining > 0:
        post_transaction(
            organization=obligation.organization,
            description=f"Waiver for {obligation.member.get_full_name()} — {reason}",
            transaction_date=datetime.date.today(),
            source=TransactionSource.WAIVER,
            posted_by=waived_by,
            event=obligation.event,
            entries=[
                {
                    "account_code": "RECV",
                    "debit_cents": 0,
                    "credit_cents": remaining,
                    "description": f"Waiver: {reason}",
                    "member": obligation.member,
                    "obligation": obligation,
                },
                {
                    "account_code": "WAIVER_EXP",
                    "debit_cents": remaining,
                    "credit_cents": 0,
                    "description": f"Waiver expense: {reason}",
                    "member": obligation.member,
                    "obligation": obligation,
                },
            ],
        )

    obligation.status = ObligationStatus.WAIVED
    obligation.waiver_reason = reason
    obligation.save(update_fields=["status", "waiver_reason", "updated_at"])
    return obligation
