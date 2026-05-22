"""
Management command: setup_founding_data

Idempotent one-time setup for the founding financial state:

  1. Record the $15,000 bereavement payout that already went out
     (DR PAYOUT_EXP $15,000 / CR CASH $15,000).

  2. Create OPEN special-contribution obligations for every active member
     to rebuild the reserve ($15,000 ÷ member_count, rounded up on remainder).

  3. Create OPEN annual maintenance-fee obligations ($50 each) for every
     active member (Article 12.2 of the bylaws).

All three operations are idempotent — re-running does nothing if the
objects already exist (identified by description + organization).

Usage:
    python manage.py setup_founding_data \\
        --death-date 2025-03-15 \\
        --bereaved-name "Lemma Household" \\
        --special-due-date 2025-05-01 \\
        --dues-due-date 2025-12-31

Options:
    --death-date DATE          Date of the death event (YYYY-MM-DD). Default: today.
    --bereaved-name NAME       Name of the bereaved household.  Required.
    --special-due-date DATE    Due date for each member's special contribution. Default: 15 days after death date.
    --dues-due-date DATE       Due date for the $50 annual maintenance fee. Default: Dec 31 of current year.
    --payout-cents INT         Payout amount in cents (default: 1500000 = $15,000).
    --dues-cents INT           Annual maintenance fee in cents (default: 5000 = $50).
    --dry-run                  Print what would happen without writing anything.
    --org-slug SLUG            Organization slug (default: addis-kidan).
"""
from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


PAYOUT_DEFAULT_CENTS = 1_500_000   # $15,000
DUES_DEFAULT_CENTS = 5_000         # $50


class Command(BaseCommand):
    help = "Record the founding death payout and create member obligations."

    def add_arguments(self, parser):
        parser.add_argument("--death-date", default="", help="Date of death event (YYYY-MM-DD).")
        parser.add_argument("--bereaved-name", default="", help="Name of the bereaved household (required).")
        parser.add_argument("--special-due-date", default="", help="Due date for special contribution (YYYY-MM-DD).")
        parser.add_argument("--dues-due-date", default="", help="Due date for $50 annual fee (YYYY-MM-DD).")
        parser.add_argument("--payout-cents", type=int, default=PAYOUT_DEFAULT_CENTS)
        parser.add_argument("--dues-cents", type=int, default=DUES_DEFAULT_CENTS)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--org-slug", default="addis-kidan")
        parser.add_argument(
            "--skip-payout", action="store_true",
            help="Skip recording the $15,000 payout (already done)."
        )
        parser.add_argument(
            "--skip-special-contribution", action="store_true",
            help="Skip creating special-contribution obligations."
        )
        parser.add_argument(
            "--skip-dues", action="store_true",
            help="Skip creating annual $50 dues obligations."
        )

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.membership.models import Member, MemberStatus
        from apps.ledger.models import (
            LedgerAccount, LedgerTransaction, LedgerEntry, TransactionSource
        )
        from apps.events.models import Event, EventType, EventStatus
        from apps.membership.models import Household
        from apps.obligations.models import Obligation, ObligationType, ObligationStatus
        from django.contrib.auth import get_user_model

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{options['org_slug']}' not found.")

        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).order_by("date_joined").first()
        if not admin_user:
            raise CommandError("No superuser found. Create one first.")

        # Parse dates
        today = date.today()
        death_date = self._parse_date(options["death_date"]) or today
        special_due_date = self._parse_date(options["special_due_date"]) or (death_date + timedelta(days=15))
        dues_due_date = self._parse_date(options["dues_due_date"]) or date(today.year, 12, 31)
        bereaved_name = options["bereaved_name"].strip()
        payout_cents = options["payout_cents"]
        dues_cents = options["dues_cents"]

        # Get active members
        active_members = list(Member.objects.filter(organization=org, status=MemberStatus.ACTIVE))
        member_count = len(active_members)
        if member_count == 0:
            self.stdout.write(self.style.WARNING("No active members found. Import members first."))
            return

        self.stdout.write(f"Organization: {org.name}")
        self.stdout.write(f"Active members: {member_count}")
        self.stdout.write(f"Death date: {death_date} | Special due: {special_due_date} | Dues due: {dues_due_date}")

        # ── Step 1: Record $15,000 payout ──────────────────────────────────────
        if not options["skip_payout"]:
            self._record_payout(
                org=org,
                admin_user=admin_user,
                bereaved_name=bereaved_name,
                death_date=death_date,
                payout_cents=payout_cents,
                dry_run=options["dry_run"],
            )

        # ── Step 2: Create special-contribution obligations ─────────────────────
        if not options["skip_special_contribution"]:
            self._create_special_contribution_obligations(
                org=org,
                active_members=active_members,
                payout_cents=payout_cents,
                bereaved_name=bereaved_name,
                death_date=death_date,
                due_date=special_due_date,
                dry_run=options["dry_run"],
            )

        # ── Step 3: Create annual $50 maintenance fee obligations ───────────────
        if not options["skip_dues"]:
            self._create_annual_dues(
                org=org,
                active_members=active_members,
                dues_cents=dues_cents,
                due_date=dues_due_date,
                year=today.year,
                dry_run=options["dry_run"],
            )

        self.stdout.write(self.style.SUCCESS("\nsetup_founding_data complete."))

    # ── helpers ────────────────────────────────────────────────────────────────

    def _parse_date(self, s):
        if not s:
            return None
        try:
            return datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"Invalid date format '{s}'. Use YYYY-MM-DD.")

    def _record_payout(self, org, admin_user, bereaved_name, death_date, payout_cents, dry_run):
        from apps.ledger.models import (
            LedgerAccount, LedgerTransaction, LedgerEntry, TransactionSource
        )
        from apps.membership.models import Household
        from apps.events.models import Event, EventType, EventStatus

        PAYOUT_DESC = f"Bereavement payout — {bereaved_name or 'founding member death event'}"

        # Idempotency check
        if LedgerTransaction.objects.filter(
            organization=org, description=PAYOUT_DESC
        ).exists():
            self.stdout.write(f"  [EXISTS] Payout ledger entry already recorded — skipping.")
            return

        if dry_run:
            self.stdout.write(f"  [DRY] Would record ${payout_cents/100:.2f} payout: {PAYOUT_DESC}")
            return

        try:
            cash_acct = LedgerAccount.objects.get(organization=org, code="CASH")
            payout_exp_acct = LedgerAccount.objects.get(organization=org, code="PAYOUT_EXP")
        except LedgerAccount.DoesNotExist as e:
            raise CommandError(f"Ledger account missing: {e}. Run bootstrap_org first.")

        # Create or find bereaved household
        if bereaved_name:
            household, _ = Household.objects.get_or_create(
                organization=org, name=bereaved_name
            )
        else:
            household = None

        # Create a closed event to represent the payout
        event, evt_created = Event.objects.get_or_create(
            organization=org,
            description=PAYOUT_DESC,
            defaults={
                "event_type": EventType.BEREAVEMENT,
                "affected_household": household or Household.objects.filter(organization=org).first(),
                "event_date": death_date,
                "payout_amount_cents": payout_cents,
                "status": EventStatus.CLOSED,
                "submitted_by": admin_user,
                "approved_by": admin_user,
                "approved_at": death_date,
                "submitted_at": death_date,
            },
        )
        status_label = "Created" if evt_created else "Exists"
        self.stdout.write(f"  [{status_label}] Event: {PAYOUT_DESC}")

        # Record the payout in the ledger
        with transaction.atomic():
            txn = LedgerTransaction.objects.create(
                organization=org,
                description=PAYOUT_DESC,
                transaction_date=death_date,
                source=TransactionSource.PAYOUT,
                posted_by=admin_user,
                event=event,
                notes=f"Founding bereavement payout of ${payout_cents/100:.2f} recorded retroactively.",
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=payout_exp_acct,
                debit_cents=payout_cents,
                description=PAYOUT_DESC,
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=cash_acct,
                credit_cents=payout_cents,
                description=PAYOUT_DESC,
            )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Payout ${payout_cents/100:,.2f} recorded in ledger."))

    def _create_special_contribution_obligations(
        self, org, active_members, payout_cents, bereaved_name, death_date, due_date, dry_run
    ):
        from apps.obligations.models import Obligation, ObligationType, ObligationStatus
        from apps.events.models import Event

        SPECIAL_DESC = f"Special contribution — {bereaved_name or 'bereavement event'}"
        member_count = len(active_members)

        # Per-member amount: ceiling division so total always >= payout
        per_member_cents = -(-payout_cents // member_count)  # ceiling division
        total = per_member_cents * member_count

        self.stdout.write(
            f"\n  Special contribution: ${payout_cents/100:,.2f} ÷ {member_count} members "
            f"= ${per_member_cents/100:.2f}/member (total ${total/100:,.2f})"
        )

        # Get the event we just created (or existing)
        event = Event.objects.filter(organization=org, description__contains=bereaved_name or "bereavement").first() if bereaved_name else None

        created_count = 0
        skipped_count = 0

        for member in active_members:
            # Idempotency: check if obligation already exists
            exists = Obligation.objects.filter(
                organization=org,
                member=member,
                obligation_type=ObligationType.EVENT,
                notes__contains=SPECIAL_DESC,
            ).exists()
            if exists:
                skipped_count += 1
                continue

            if dry_run:
                created_count += 1
                continue

            Obligation.objects.create(
                organization=org,
                obligation_type=ObligationType.EVENT,
                member=member,
                event=event,
                amount_cents=per_member_cents,
                due_date=due_date,
                status=ObligationStatus.OPEN,
                notes=SPECIAL_DESC,
            )
            created_count += 1

        if dry_run:
            self.stdout.write(f"  [DRY] Would create {created_count} special-contribution obligations.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] Created {created_count} obligations, skipped {skipped_count} (already existed)."
                )
            )

    def _create_annual_dues(self, org, active_members, dues_cents, due_date, year, dry_run):
        from apps.obligations.models import Obligation, ObligationType, ObligationStatus

        DUES_DESC = f"Annual maintenance fee {year}"
        member_count = len(active_members)

        self.stdout.write(f"\n  Annual dues: ${dues_cents/100:.2f} × {member_count} members (due {due_date})")

        created_count = 0
        skipped_count = 0

        for member in active_members:
            exists = Obligation.objects.filter(
                organization=org,
                member=member,
                obligation_type=ObligationType.DUES,
                notes__contains=DUES_DESC,
            ).exists()
            if exists:
                skipped_count += 1
                continue

            if dry_run:
                created_count += 1
                continue

            Obligation.objects.create(
                organization=org,
                obligation_type=ObligationType.DUES,
                member=member,
                amount_cents=dues_cents,
                due_date=due_date,
                status=ObligationStatus.OPEN,
                notes=DUES_DESC,
            )
            created_count += 1

        if dry_run:
            self.stdout.write(f"  [DRY] Would create {created_count} annual dues obligations.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] Created {created_count} dues, skipped {skipped_count} (already existed)."
                )
            )
