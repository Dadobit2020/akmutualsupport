"""
Management command: import_payment_members

Imports members from the payment CSV (generated from the PDF member payment list).
Unlike import_members (which always records $200), this command records the
ACTUAL amount paid from the CSV (Zelle/cash/check, $100–$800).

CSV columns required:
  first_name, last_name, join_date

CSV columns optional:
  phone, payment_date, payment_method, payment_reference, amount_paid, notes

Usage:
    python manage.py import_payment_members payment_members_import.csv
    python manage.py import_payment_members payment_members_import.csv --dry-run
    python manage.py import_payment_members payment_members_import.csv --org-slug addis-kidan
"""
import csv
import decimal
from datetime import date, datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Import members from payment CSV with actual payment amounts."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to payment_members_import.csv")
        parser.add_argument("--org-slug", default="addis-kidan")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.membership.models import Member, MemberStatus, MembershipTier
        from apps.ledger.models import LedgerAccount, LedgerTransaction, LedgerEntry, TransactionSource
        from apps.obligations.models import Payment

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{options['org_slug']}' not found. Run bootstrap_org first.")

        User = get_user_model()
        system_user = User.objects.filter(is_superuser=True).order_by("created_at").first()
        if not system_user:
            raise CommandError("No superuser found. Run createsuperuser first.")

        try:
            cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
            revenue_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
        except LedgerAccount.DoesNotExist as e:
            raise CommandError(f"Ledger account missing: {e}. Run bootstrap_org first.")

        try:
            with open(options["csv_file"], newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['csv_file']}")

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved.\n"))

        self.stdout.write(f"Processing {len(rows)} rows from {options['csv_file']}\n")

        created = skipped = errors = 0
        total_cents = 0

        for i, row in enumerate(rows, start=2):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}

            first_name = row.get("first_name", "").title()
            last_name = row.get("last_name", "").title()
            if not first_name or not last_name:
                self.stderr.write(f"  [Row {i}] Missing name — skipped.")
                errors += 1
                continue

            # Parse join_date
            raw_date = row.get("join_date") or row.get("payment_date") or ""
            join_date = self._parse_date(raw_date) or date(2024, 7, 1)
            payment_date = self._parse_date(row.get("payment_date") or raw_date) or join_date

            # Parse amount
            try:
                amount_cents = int(decimal.Decimal(row.get("amount_paid", "200").replace(",", "")) * 100)
            except Exception:
                amount_cents = 20000
            if amount_cents <= 0:
                self.stdout.write(f"  [Skip  ] {first_name} {last_name} — zero/negative amount.")
                skipped += 1
                continue

            method = (row.get("payment_method") or "zelle").lower().strip()
            if method not in ("cash", "check", "zelle", "online", "bank_transfer", "other"):
                method = "zelle"
            reference = row.get("payment_reference", "").strip()
            phone = row.get("phone", "").strip()
            notes = row.get("notes", "").strip()

            # Duplicate check
            exists = Member.objects.filter(
                organization=org,
                first_name__iexact=first_name,
                last_name__iexact=last_name,
            ).exists()
            if exists:
                self.stdout.write(f"  [Exists ] {first_name} {last_name}")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DryRun] {first_name} {last_name} | "
                    f"${amount_cents/100:.2f} {method} {reference} | {payment_date}"
                )
                created += 1
                total_cents += amount_cents
                continue

            try:
                with transaction.atomic():
                    member = Member.objects.create(
                        organization=org,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone,
                        join_date=join_date,
                        status=MemberStatus.ACTIVE,
                        tier=MembershipTier.STANDARD,
                        notes=notes,
                    )

                    txn = LedgerTransaction.objects.create(
                        organization=org,
                        description=f"Registration payment — {first_name} {last_name}",
                        transaction_date=payment_date,
                        source=TransactionSource.PAYMENT,
                        posted_by=system_user,
                        notes=f"Imported from PDF payment list. Method: {method}. Ref: {reference}",
                    )
                    LedgerEntry.objects.create(
                        ledger_transaction=txn,
                        account=cash_account,
                        debit_cents=amount_cents,
                        description=f"{method.title()} payment received",
                        member=member,
                    )
                    LedgerEntry.objects.create(
                        ledger_transaction=txn,
                        account=revenue_account,
                        credit_cents=amount_cents,
                        description=f"Registration fee revenue",
                        member=member,
                    )
                    Payment.objects.create(
                        organization=org,
                        member=member,
                        amount_cents=amount_cents,
                        payment_date=payment_date,
                        method=method,
                        reference=reference or f"PDF-{first_name[:2].upper()}{last_name[:3].upper()}",
                        notes=notes or "Imported from PDF payment list.",
                        ledger_transaction=txn,
                    )

                    self.stdout.write(
                        f"  [Created] {first_name} {last_name} | "
                        f"${amount_cents/100:.2f} {method} | {payment_date}"
                    )
                    created += 1
                    total_cents += amount_cents

            except Exception as exc:
                self.stderr.write(f"  [Error  ] {first_name} {last_name}: {exc}")
                errors += 1

        self.stdout.write("\n" + "─" * 55)
        summary = (
            f"{'DRY RUN ' if dry_run else ''}"
            f"{created} created, {skipped} skipped, {errors} errors. "
            f"Total: ${total_cents/100:,.2f}"
        )
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style(summary))

    def _parse_date(self, raw):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except (ValueError, AttributeError):
                pass
        return None
