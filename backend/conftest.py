"""
Shared pytest fixtures for the entire test suite.
"""
import datetime
import pytest
from apps.identity.models import Organization, User
from apps.membership.models import Member, Household
from apps.ledger.models import LedgerAccount, LedgerTransaction, LedgerEntry


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Test Org",
        slug="test-org",
        default_payout_amount_cents=100000,
        contribution_deadline_days=30,
    )


@pytest.fixture
def user(db, organization):
    return User.objects.create_user(
        email="treasurer@test.org",
        password="testpassword123",
        first_name="Test",
        last_name="Treasurer",
    )


@pytest.fixture
def household(db, organization):
    h = Household.objects.create(organization=organization, name="Smith Household")
    return h


@pytest.fixture
def member(db, organization, household):
    return Member.objects.create(
        organization=organization,
        first_name="John",
        last_name="Smith",
        household=household,
        join_date=datetime.date(2023, 1, 1),
    )


@pytest.fixture
def cash_account(db, organization):
    return LedgerAccount.objects.create(
        organization=organization,
        code="CASH",
        name="Cash & Bank",
        account_type="asset",
    )


@pytest.fixture
def recv_account(db, organization):
    return LedgerAccount.objects.create(
        organization=organization,
        code="RECV",
        name="Member Receivables",
        account_type="asset",
    )


@pytest.fixture
def ledger_account(db, organization):
    return LedgerAccount.objects.create(
        organization=organization,
        code="TEST",
        name="Test Account",
        account_type="asset",
    )


@pytest.fixture
def ledger_transaction(db, organization, user, ledger_account):
    txn = LedgerTransaction.objects.create(
        organization=organization,
        description="Test transaction",
        transaction_date=datetime.date.today(),
        source="manual",
        posted_by=user,
    )
    return txn


@pytest.fixture
def ledger_entry(db, ledger_transaction, ledger_account):
    return LedgerEntry.objects.create(
        ledger_transaction=ledger_transaction,
        account=ledger_account,
        debit_cents=100,
        credit_cents=0,
    )
