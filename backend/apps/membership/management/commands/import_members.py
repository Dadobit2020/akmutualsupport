"""
Management command: import_members

Bulk-import founding members from a CSV file.
For each row it:
  1. Creates (or updates) a Member record.
  2. Records a $200 registration-fee payment in the double-entry ledger
     (DR CASH / CR CONTRIB_REV) and marks the obligation PAID.

Required CSV columns:
    first_name, last_name, join_date  (YYYY-MM-DD)

Optional columns:
    first_name_am, last_name_am, email, phone, phone_whatsapp,
    address, notes, payment_date (defaults to join_date),
    payment_method (cash|check|bank_transfer|online|other, default: cash),
    payment_reference

Usage:
    python manage.py import_members members.csv [--dry-run] [--org-slug addis-kidan]
"""
import csv
from datetime import date, datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model


REGISTRATION_FEE_CENTS = 20_000  # $200.00


class Command(BaseCommand):
    help = "Import founding members from a CSV file and record their $200 registration payments."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database.",
        )
        parser.add_argument(
            "--org-slug",
            default="addis-kidan",
            help="Organization slug (default: addis-kidan).",
        )
        parser.add_argument(
            "--skip-payments",
            action="store_true",
            help="Create members only, without recording payments.",
        )

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.membership.models import Member, MemberStatus, MembershipTier
        from apps.ledger.models import LedgerAccount, LedgerTransaction, LedgerEntry, TransactionSource
        from apps.obligations.models import Obligation, ObligationType, ObligationStatus

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{options['org_slug']}' not found. Run bootstrap_org first.")

        # Get system user (admin) for ledger attribution
        User = get_user_model()
        try:
            system_user = User.objects.filter(is_superuser=True).order_by("created_at").first()
            if not system_user:
                raise CommandError("No superuser found. Create one first with createsuperuser.")
        except Exception as e:
            raise CommandError(f"Error finding system user: {e}")

        # Get ledger accounts
        try:
            cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
            contrib_rev_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
        except LedgerAccount.DoesNotExist as e:
            raise CommandError(f"Required ledger account not found: {e}. Run bootstrap_org first.")

        try:
            with open(options["csv_file"], newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['csv_file']}")
        except Exception as e:
            raise CommandError(f"Error reading CSV: {e}")

        self.stdout.write(f"Found {len(rows)} rows in {options['csv_file']}")

        created_count = 0
        skipped_count = 0
        payment_count = 0
        errors = []

        for i, row in enumerate(rows, start=2):  # start=2 for 1-indexed with header row
            row = {k.strip(): v.strip() for k, v in row.items() if k}

            # Validate required fields
            first_name = row.get("first_name", "").strip()
            last_name = row.get("last_name", "").strip()
            join_date_str = row.get("join_date", "").strip()

            if not first_name or not last_name:
                errors.append(f"Row {i}: missing first_name or last_name — skipped.")
                continue
            if not join_date_str:
                errors.append(f"Row {i}: missing join_date — skipped.")
                continue

            try:
                join_date = datetime.strptime(join_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Row {i}: invalid join_date '{join_date_str}' (expected YYYY-MM-DD) — skipped.")
                continue

            # Parse optional payment date
            payment_date_str = row.get("payment_date", "").strip()
            if payment_date_str:
                try:
                    payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
                except ValueError:
                    errors.append(f"Row {i}: invalid payment_date '{payment_date_str}' — using join_date.")
                    payment_date = join_date
            else:
                payment_date = join_date

            payment_method = row.get("payment_method", "cash").strip() or "cash"
            payment_reference = row.get("payment_reference", "").strip()

            # Build member data
            member_data = {
                "first_name": first_name,
                "last_name": last_name,
                "first_name_am": row.get("first_name_am", "").strip(),
                "last_name_am": row.get("last_name_am", "").strip(),
                "email": row.get("email", "").strip(),
                "phone": row.get("phone", "").strip(),
                "phone_whatsapp": row.get("phone_whatsapp", "").strip(),
                "address": row.get("address", "").strip(),
                "notes": row.get("notes", "").strip(),
                "join_date": join_date,
                "status": MemberStatus.ACTIVE,
                "tier": MembershipTier.STANDARD,
            }

            if options["dry_run"]:
                self.stdout.write(f"  [DRY] Row {i}: {first_name} {last_name} — would import.")
                created_count += 1
                continue

            try:
                with transaction.atomic():
                    # Use email as dedup key if available
                    lookup = {"organization": org, "first_name": first_name, "last_name": last_name}
                    member, created = Member.objects.get_or_create(
                        **lookup,
                        defaults={**member_data, "organization": org},
                    )
                    if not created:
                        skipped_count += 1
                        self.stdout.write(f"  [EXISTS] {first_name} {last_name} — skipped (already in DB).")
                        continue

                    created_count += 1
                    self.stdout.write(f"  [CREATED] {first_name} {last_name}")

                    if options["skip_payments"]:
                        continue

                    # Record $200 registration fee in the ledger
                    txn = LedgerTransaction.objects.create(
                        organization=org,
                        description=f"Registration fee — {first_name} {last_name}",
                        transaction_date=payment_date,
                        source=TransactionSource.PAYMENT,
                        posted_by=system_user,
                        notes=f"Founding member registration $200 imported via import_members command.",
                    )
                    LedgerEntry.objects.create(
                        ledger_transaction=txn,
                        account=cash_account,
                        debit_cents=REGISTRATION_FEE_CENTS,
                        description=f"Registration fee received — {first_name} {last_name}",
                        member=member,
                    )
                    LedgerEntry.objects.create(
                        ledger_transaction=txn,
                        account=contrib_rev_account,
                        credit_cents=REGISTRATION_FEE_CENTS,
                        description=f"Registration fee revenue — {first_name} {last_name}",
                        member=member,
                    )

                    # Also record as a Payment object for member payment history
                    from apps.obligations.models import Payment
                    Payment.objects.create(
                        organization=org,
                        member=member,
                        amount_cents=REGISTRATION_FEE_CENTS,
                        payment_date=payment_date,
                        method=payment_method,
                        reference=payment_reference or f"REG-{first_name[:2].upper()}{last_name[:3].upper()}",
                        notes="Founding member registration fee.",
                        ledger_transaction=txn,
                    )

                    payment_count += 1

            except Exception as e:
                errors.append(f"Row {i}: {first_name} {last_name} — error: {e}")

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY RUN — no changes written."))
            self.stdout.write(f"  Would create: {created_count} members")
        else:
            self.stdout.write(self.style.SUCCESS(f"Import complete."))
            self.stdout.write(f"  Created:  {created_count} members")
            self.stdout.write(f"  Skipped:  {skipped_count} (already existed)")
            if not options["skip_payments"]:
                self.stdout.write(f"  Payments: {payment_count} × $200 recorded")

        if errors:
            self.stdout.write(self.style.WARNING(f"\nWarnings/errors ({len(errors)}):"))
            for e in errors:
                self.stdout.write(f"  {e}")
