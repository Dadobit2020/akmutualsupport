"""
Ledger tests — exhaustive coverage of the financial core.
Every money-touching code path requires tests (see plan Section 23).
"""
import datetime
import pytest
from django.core.exceptions import ValidationError

from apps.ledger.models import LedgerEntry, LedgerTransaction, LedgerAccount
from apps.ledger.service import post_transaction, post_reversal, get_member_balance_cents


@pytest.mark.django_db
class TestLedgerEntryImmutability:
    def test_entry_cannot_be_updated(self, ledger_entry):
        with pytest.raises(ValidationError, match="immutable"):
            ledger_entry.description = "tampered"
            ledger_entry.save()

    def test_entry_cannot_be_deleted(self, ledger_entry):
        with pytest.raises(ValidationError, match="cannot be deleted"):
            ledger_entry.delete()

    def test_entry_requires_nonzero_amount(self, organization, ledger_account, ledger_transaction):
        with pytest.raises(ValidationError):
            LedgerEntry.objects.create(
                ledger_transaction=ledger_transaction,
                account=ledger_account,
                debit_cents=0,
                credit_cents=0,
            )

    def test_entry_cannot_have_both_debit_and_credit(self, organization, ledger_account, ledger_transaction):
        with pytest.raises(ValidationError):
            LedgerEntry.objects.create(
                ledger_transaction=ledger_transaction,
                account=ledger_account,
                debit_cents=100,
                credit_cents=100,
            )


@pytest.mark.django_db
class TestPostTransaction:
    def test_balanced_transaction_succeeds(self, organization, user, cash_account, recv_account):
        txn = post_transaction(
            organization=organization,
            description="Test payment",
            transaction_date=datetime.date.today(),
            source="manual",
            posted_by=user,
            entries=[
                {"account_code": "CASH", "debit_cents": 5000, "credit_cents": 0},
                {"account_code": "RECV", "debit_cents": 0, "credit_cents": 5000},
            ],
        )
        assert txn.pk is not None
        assert txn.entries.count() == 2
        total_dr = sum(e.debit_cents for e in txn.entries.all())
        total_cr = sum(e.credit_cents for e in txn.entries.all())
        assert total_dr == total_cr == 5000

    def test_unbalanced_transaction_raises(self, organization, user):
        with pytest.raises(ValidationError, match="does not balance"):
            post_transaction(
                organization=organization,
                description="Unbalanced",
                transaction_date=datetime.date.today(),
                source="manual",
                posted_by=user,
                entries=[
                    {"account_code": "CASH", "debit_cents": 5000, "credit_cents": 0},
                    {"account_code": "RECV", "debit_cents": 0, "credit_cents": 4999},
                ],
            )

    def test_zero_amount_transaction_raises(self, organization, user):
        with pytest.raises(ValidationError, match="non-zero"):
            post_transaction(
                organization=organization,
                description="Zero",
                transaction_date=datetime.date.today(),
                source="manual",
                posted_by=user,
                entries=[
                    {"account_code": "CASH", "debit_cents": 0, "credit_cents": 0},
                    {"account_code": "RECV", "debit_cents": 0, "credit_cents": 0},
                ],
            )

    def test_reversal_posts_compensating_entries(self, organization, user, cash_account, recv_account):
        original = post_transaction(
            organization=organization,
            description="Original",
            transaction_date=datetime.date.today(),
            source="manual",
            posted_by=user,
            entries=[
                {"account_code": "CASH", "debit_cents": 1000, "credit_cents": 0},
                {"account_code": "RECV", "debit_cents": 0, "credit_cents": 1000},
            ],
        )
        reversal = post_reversal(original_txn=original, posted_by=user, reason="Test reversal")
        # Reversal entries should be swapped
        rev_entries = list(reversal.entries.all())
        orig_entries = list(original.entries.all())
        for orig, rev in zip(orig_entries, rev_entries):
            assert orig.debit_cents == rev.credit_cents
            assert orig.credit_cents == rev.debit_cents

    def test_cannot_reverse_already_reversed_transaction(self, organization, user, cash_account, recv_account):
        original = post_transaction(
            organization=organization,
            description="Original",
            transaction_date=datetime.date.today(),
            source="manual",
            posted_by=user,
            entries=[
                {"account_code": "CASH", "debit_cents": 1000, "credit_cents": 0},
                {"account_code": "RECV", "debit_cents": 0, "credit_cents": 1000},
            ],
        )
        post_reversal(original_txn=original, posted_by=user, reason="First reversal")
        with pytest.raises(ValidationError, match="already been reversed"):
            post_reversal(original_txn=original, posted_by=user, reason="Second reversal")


@pytest.mark.django_db
class TestMemberBalance:
    def test_member_balance_reflects_obligation_and_payment(
        self, organization, user, member, cash_account, recv_account
    ):
        # Post obligation (DR RECV)
        post_transaction(
            organization=organization,
            description="Obligation",
            transaction_date=datetime.date.today(),
            source="event_obligation",
            posted_by=user,
            entries=[
                {"account_code": "RECV", "debit_cents": 10000, "credit_cents": 0, "member": member},
                {"account_code": "CASH", "debit_cents": 0, "credit_cents": 10000},
            ],
        )
        balance = get_member_balance_cents(member, organization)
        assert balance == 10000

        # Post payment (CR RECV)
        post_transaction(
            organization=organization,
            description="Payment",
            transaction_date=datetime.date.today(),
            source="payment",
            posted_by=user,
            entries=[
                {"account_code": "CASH", "debit_cents": 10000, "credit_cents": 0},
                {"account_code": "RECV", "debit_cents": 0, "credit_cents": 10000, "member": member},
            ],
        )
        balance = get_member_balance_cents(member, organization)
        assert balance == 0

    def test_partial_payment_leaves_correct_balance(
        self, organization, user, member, cash_account, recv_account
    ):
        post_transaction(
            organization=organization,
            description="Obligation",
            transaction_date=datetime.date.today(),
            source="event_obligation",
            posted_by=user,
            entries=[
                {"account_code": "RECV", "debit_cents": 10000, "credit_cents": 0, "member": member},
                {"account_code": "CASH", "debit_cents": 0, "credit_cents": 10000},
            ],
        )
        post_transaction(
            organization=organization,
            description="Partial payment",
            transaction_date=datetime.date.today(),
            source="payment",
            posted_by=user,
            entries=[
                {"account_code": "CASH", "debit_cents": 6000, "credit_cents": 0},
                {"account_code": "RECV", "debit_cents": 0, "credit_cents": 6000, "member": member},
            ],
        )
        balance = get_member_balance_cents(member, organization)
        assert balance == 4000
