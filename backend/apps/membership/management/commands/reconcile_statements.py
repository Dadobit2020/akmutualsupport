"""
Management command: reconcile_statements

Imports Wells Fargo bank transactions from bank_transactions_all.csv and:
  1. Records member Zelle payments (matches by name → auto-applies to open obligations)
  2. Records the Feb 2026 $15,000 bereavement payout (Check #1004)
  3. Records refund payouts (Mulu Hagos, Fikre Dante, Ermias Getachew, Elsabeth Gebertansaye)
  4. Deactivates the 4 non-qualifying members whose money was refunded

Usage:
    python manage.py reconcile_statements bank_transactions_all.csv [--dry-run] [--org-slug addis-kidan]
"""
import csv
import re
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model


# Members whose registration was refunded — they do not qualify for coverage
NON_QUALIFYING = [
    {"first_name": "Mulu",    "last_name": "Hagos"},
    {"first_name": "Fikre",   "last_name": "Dante"},
    {"first_name": "Ermias",  "last_name": "Getachew"},
    {"first_name": "Elsabet", "last_name": "Gebertansaye"},
]


class Command(BaseCommand):
    help = "Import bank statement transactions and reconcile member payments."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to bank_transactions_all.csv")
        parser.add_argument("--org-slug", default="addis-kidan")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.membership.models import Member, MemberStatus
        from apps.obligations.models import Obligation, ObligationStatus, Payment
        from apps.ledger.models import (
            LedgerAccount, LedgerTransaction, LedgerEntry, TransactionSource,
        )

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{options['org_slug']}' not found.")

        User = get_user_model()
        system_user = User.objects.filter(is_superuser=True).order_by("created_at").first()
        if not system_user:
            raise CommandError("No superuser found.")

        try:
            cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
            contrib_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
            payout_account = LedgerAccount.objects.get(organization=org, code="PAYOUT_EXP")
        except LedgerAccount.DoesNotExist as e:
            raise CommandError(f"Ledger account missing: {e}. Run bootstrap_org first.")

        # Build member name index for matching
        all_members = list(Member.objects.filter(organization=org))
        member_index = self._build_index(all_members)

        try:
            with open(options["csv_file"], newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['csv_file']}")

        self.stdout.write(f"Processing {len(rows)} transactions...\n")

        stats = {"payments": 0, "payouts": 0, "skipped": 0, "unmatched": 0, "deactivated": 0}

        # ── Step 1: Deactivate non-qualifying members ──────────────────────────
        self.stdout.write("─── Non-qualifying members (refunded) ───")
        for nq in NON_QUALIFYING:
            candidates = Member.objects.filter(
                organization=org,
                first_name__iexact=nq["first_name"],
                last_name__icontains=nq["last_name"][:4],
            )
            if not candidates.exists():
                # Try partial match
                candidates = Member.objects.filter(
                    organization=org,
                    last_name__icontains=nq["last_name"][:4],
                )
            if candidates.exists():
                for m in candidates:
                    msg = f"  DEACTIVATE: {m.first_name} {m.last_name} → status=left"
                    if dry_run:
                        self.stdout.write(f"  [DRY] {msg}")
                    else:
                        m.status = MemberStatus.LEFT
                        m.notes = (m.notes or "") + " | Refunded — did not qualify for coverage."
                        m.save(update_fields=["status", "notes", "updated_at"])
                        self.stdout.write(self.style.WARNING(msg))
                    stats["deactivated"] += 1
            else:
                self.stdout.write(f"  [NOT FOUND] {nq['first_name']} {nq['last_name']}")
        self.stdout.write("")

        # ── Step 2: Process each transaction ──────────────────────────────────
        self.stdout.write("─── Bank transactions ───")
        for row in rows:
            txn_type = row.get("type", "").strip()
            date_str = row.get("date", "").strip()
            credit = float(row.get("credit", 0) or 0)
            debit = float(row.get("debit", 0) or 0)
            amount_cents = int(row.get("amount_cents", 0) or 0)
            member_name = row.get("member_name", "").strip()
            description = row.get("description", "").strip()
            memo = row.get("memo", "").strip()
            reference = row.get("reference", "").strip()

            try:
                txn_date = date.fromisoformat(date_str)
            except ValueError:
                stats["skipped"] += 1
                continue

            if amount_cents <= 0:
                stats["skipped"] += 1
                continue

            # ── Member payments (Zelle From / Tithe.ly) ───────────────────────
            if txn_type in ("member_payment", "tithe_ly", "cash_deposit") and credit > 0:
                # Try to match member
                member = None
                if member_name and member_name != "Tithe.ly Batch":
                    member = self._match_member(member_name, member_index)

                if not member and txn_type in ("tithe_ly", "cash_deposit"):
                    # Batch / cash deposit — record without member linkage
                    if dry_run:
                        self.stdout.write(
                            f"  [DRY] BATCH ${credit:.2f} {txn_type} {date_str}"
                        )
                    else:
                        self._record_payment(
                            org, None, cash_account, contrib_account,
                            amount_cents, txn_date, "online" if "tithe" in txn_type else "cash",
                            reference, description, system_user,
                        )
                    stats["payments"] += 1
                    continue

                if not member:
                    self.stdout.write(
                        f"  [UNMATCHED] ${credit:.2f} on {date_str} — '{member_name}'"
                    )
                    stats["unmatched"] += 1
                    continue

                # Skip if payment already recorded for this member + date + amount
                if Payment.objects.filter(
                    organization=org,
                    member=member,
                    amount_cents=amount_cents,
                    payment_date=txn_date,
                ).exists():
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] PAYMENT ${credit:.2f} → {member.first_name} {member.last_name}"
                    )
                else:
                    self._record_payment(
                        org, member, cash_account, contrib_account,
                        amount_cents, txn_date, "other",
                        reference, description or memo, system_user,
                    )
                    self.stdout.write(
                        f"  [OK] PAYMENT ${credit:.2f} → {member.first_name} {member.last_name}"
                    )
                stats["payments"] += 1

            # ── Check outgoing ($15k payout) ──────────────────────────────────
            elif txn_type == "check_out" and debit > 0:
                if debit == 15000.00:
                    label = "Bereavement Payout — Check #1004"
                    method_desc = "Check #1004"
                else:
                    label = description or "Check payment"
                    method_desc = reference or ""

                if dry_run:
                    self.stdout.write(f"  [DRY] PAYOUT ${debit:.2f} — {label}")
                else:
                    if not LedgerTransaction.objects.filter(
                        organization=org,
                        source=TransactionSource.PAYOUT,
                        transaction_date=txn_date,
                        description__icontains="Check #1004" if debit == 15000 else label[:20],
                    ).exists():
                        self._record_payout(
                            org, payout_account, cash_account,
                            amount_cents, txn_date, label, method_desc, system_user,
                        )
                        self.stdout.write(f"  [OK] PAYOUT ${debit:.2f} — {label}")
                    else:
                        self.stdout.write(f"  [SKIP] PAYOUT already recorded — ${debit:.2f}")
                stats["payouts"] += 1

            # ── Refunds out ────────────────────────────────────────────────────
            elif txn_type == "refund_out" and debit > 0:
                label = f"Refund — {member_name or description}"
                if dry_run:
                    self.stdout.write(f"  [DRY] REFUND ${debit:.2f} — {label}  memo: {memo}")
                else:
                    if not LedgerTransaction.objects.filter(
                        organization=org,
                        source=TransactionSource.PAYOUT,
                        transaction_date=txn_date,
                        description__icontains=member_name[:10] if member_name else label[:10],
                    ).exists():
                        self._record_payout(
                            org, payout_account, cash_account,
                            amount_cents, txn_date, label,
                            reference or memo, system_user,
                        )
                        self.stdout.write(f"  [OK] REFUND ${debit:.2f} — {label}")
                    else:
                        self.stdout.write(f"  [SKIP] REFUND already recorded — {label}")
                stats["payouts"] += 1
            else:
                stats["skipped"] += 1

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 55)
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style(
            f"{'DRY RUN ' if dry_run else ''}Complete.\n"
            f"  Payments recorded:        {stats['payments']}\n"
            f"  Payouts/refunds recorded: {stats['payouts']}\n"
            f"  Members deactivated:      {stats['deactivated']}\n"
            f"  Unmatched (manual needed): {stats['unmatched']}\n"
            f"  Skipped:                  {stats['skipped']}"
        ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_index(self, members):
        """Build a dict of normalized_name → member for fast lookup."""
        idx = {}
        for m in members:
            key = self._normalize(f"{m.first_name} {m.last_name}")
            idx[key] = m
            # Also index reversed (last first)
            idx[self._normalize(f"{m.last_name} {m.first_name}")] = m
        return idx

    @staticmethod
    def _normalize(name):
        return re.sub(r"[^a-z]", "", name.lower())

    def _match_member(self, bank_name, index):
        """Try to match bank_name to a member."""
        # Strip bank metadata (Ref #, dates, notes)
        clean = re.sub(r"\s+(Ref|on|Payment|Annual|Yearly|Zelle|From).*", "", bank_name, flags=re.I)
        clean = clean.strip()
        norm = self._normalize(clean)

        # Exact full-name match
        if norm in index:
            return index[norm]

        # Try matching by tokens: look for members whose first+last are substrings
        words = [w for w in re.split(r"\s+", clean.lower()) if len(w) > 2]
        best = None
        best_score = 0
        for key, member in index.items():
            fn = self._normalize(member.first_name)
            ln = self._normalize(member.last_name)
            score = 0
            for w in words:
                wn = self._normalize(w)
                if fn.startswith(wn[:4]) or wn.startswith(fn[:4]):
                    score += 2
                if ln.startswith(wn[:4]) or wn.startswith(ln[:4]):
                    score += 2
            if score >= 4 and score > best_score:
                best_score = score
                best = member

        return best

    def _record_payment(self, org, member, cash_acct, contrib_acct,
                        amount_cents, pay_date, method, reference, notes, posted_by):
        from apps.obligations.models import Obligation, ObligationStatus, Payment
        from apps.ledger.models import LedgerTransaction, LedgerEntry, TransactionSource

        with transaction.atomic():
            txn = LedgerTransaction.objects.create(
                organization=org,
                description=f"Payment — {member.get_full_name() if member else 'Batch'} {reference}".strip(),
                transaction_date=pay_date,
                source=TransactionSource.PAYMENT,
                posted_by=posted_by,
                notes=notes,
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=cash_acct,
                debit_cents=amount_cents,
                credit_cents=0,
                member=member,
                description="Cash/Zelle receipt",
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=contrib_acct,
                debit_cents=0,
                credit_cents=amount_cents,
                member=member,
                description="Contribution revenue",
            )
            payment = Payment.objects.create(
                organization=org,
                member=member,
                amount_cents=amount_cents,
                payment_date=pay_date,
                method=method,
                reference=reference,
                notes=notes,
                ledger_transaction=txn,
            )
            # Auto-apply to oldest open obligations
            if member:
                remaining = amount_cents
                for ob in Obligation.objects.filter(
                    member=member,
                    status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
                ).order_by("due_date"):
                    if remaining <= 0:
                        break
                    apply = min(remaining, ob.outstanding_cents)
                    if apply > 0:
                        ob.apply_payment_cents(apply)
                        remaining -= apply

    def _record_payout(self, org, payout_acct, cash_acct,
                       amount_cents, pay_date, description, reference, posted_by):
        from apps.ledger.models import LedgerTransaction, LedgerEntry, TransactionSource

        with transaction.atomic():
            txn = LedgerTransaction.objects.create(
                organization=org,
                description=description,
                transaction_date=pay_date,
                source=TransactionSource.PAYOUT,
                posted_by=posted_by,
                notes=reference,
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=payout_acct,
                debit_cents=amount_cents,
                credit_cents=0,
                description=description,
            )
            LedgerEntry.objects.create(
                ledger_transaction=txn,
                account=cash_acct,
                debit_cents=0,
                credit_cents=amount_cents,
                description=f"Cash out — {reference}",
            )
