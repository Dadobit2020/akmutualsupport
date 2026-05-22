"""
Ledger service — the ONLY way other modules should write financial state.

All money movements go through post_transaction(). Other modules never touch
LedgerEntry directly.
"""
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from .models import LedgerTransaction, LedgerEntry, LedgerAccount, TransactionSource
import datetime


def post_transaction(
    *,
    organization,
    description: str,
    transaction_date: datetime.date,
    source: str,
    posted_by,
    entries: list[dict],
    event=None,
    reverses=None,
    notes: str = "",
) -> LedgerTransaction:
    """
    Create a balanced ledger transaction.

    `entries` is a list of dicts:
        {
            "account_code": str,          # e.g. "CASH"
            "debit_cents": int,           # 0 if credit side
            "credit_cents": int,          # 0 if debit side
            "description": str,           # optional
            "member": Member | None,
            "obligation": Obligation | None,
        }

    Raises ValidationError if the transaction does not balance.
    """
    if not entries:
        raise ValidationError("A transaction must have at least two entries.")

    total_debits = sum(e.get("debit_cents", 0) for e in entries)
    total_credits = sum(e.get("credit_cents", 0) for e in entries)
    if total_debits != total_credits:
        raise ValidationError(
            f"Transaction does not balance: debits={total_debits} credits={total_credits}"
        )
    if total_debits == 0:
        raise ValidationError("Transaction amount must be non-zero.")

    with db_transaction.atomic():
        txn = LedgerTransaction.objects.create(
            organization=organization,
            description=description,
            transaction_date=transaction_date,
            source=source,
            posted_by=posted_by,
            event=event,
            reverses=reverses,
            notes=notes,
        )

        account_cache = {}
        for entry_data in entries:
            code = entry_data["account_code"]
            if code not in account_cache:
                account_cache[code] = LedgerAccount.objects.get(
                    organization=organization, code=code
                )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=account_cache[code],
                debit_cents=entry_data.get("debit_cents", 0),
                credit_cents=entry_data.get("credit_cents", 0),
                description=entry_data.get("description", ""),
                member=entry_data.get("member"),
                obligation=entry_data.get("obligation"),
            )

        return txn


def post_reversal(
    *,
    original_txn: LedgerTransaction,
    posted_by,
    reason: str,
) -> LedgerTransaction:
    """
    Reverse a posted transaction by posting compensating entries.
    The original transaction is preserved. The new transaction references it via `reverses`.
    """
    if hasattr(original_txn, "reversed_by"):
        raise ValidationError(f"Transaction {original_txn.id} has already been reversed.")

    reversed_entries = []
    for entry in original_txn.entries.all():
        reversed_entries.append({
            "account_code": entry.account.code,
            "debit_cents": entry.credit_cents,
            "credit_cents": entry.debit_cents,
            "description": f"Reversal: {entry.description}",
            "member": entry.member,
            "obligation": entry.obligation,
        })

    return post_transaction(
        organization=original_txn.organization,
        description=f"REVERSAL of: {original_txn.description}. Reason: {reason}",
        transaction_date=datetime.date.today(),
        source=TransactionSource.REVERSAL,
        posted_by=posted_by,
        entries=reversed_entries,
        event=original_txn.event,
        reverses=original_txn,
        notes=f"Reversal reason: {reason}",
    )


def get_member_balance_cents(member, organization, as_of_date=None) -> int:
    """
    Derive a member's net balance from the ledger.
    Positive = member owes money (debit balance on receivables).
    Never reads a stored balance field.
    """
    from django.db.models import Sum
    qs = LedgerEntry.objects.filter(
        member=member,
        account__organization=organization,
        account__code="RECV",  # Member Receivables account
    )
    if as_of_date:
        qs = qs.filter(ledger_transaction__transaction_date__lte=as_of_date)

    totals = qs.aggregate(
        total_debit=Sum("debit_cents"),
        total_credit=Sum("credit_cents"),
    )
    return (totals["total_debit"] or 0) - (totals["total_credit"] or 0)
