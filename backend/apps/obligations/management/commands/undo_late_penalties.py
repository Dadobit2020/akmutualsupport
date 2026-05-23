"""
Management command: undo_late_penalties

Reverses everything apply_late_penalties did:
  - Restores penalty-inflated obligation amounts back to original_amount_cents
  - Clears penalty_weeks_applied
  - Reactivates members who were auto-suspended by the penalty run
"""
import re
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Undo all changes made by apply_late_penalties."

    def add_arguments(self, parser):
        parser.add_argument("--org-slug", default="addis-kidan")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.obligations.models import Obligation
        from apps.membership.models import Member, MemberStatus

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Organization '{options['org_slug']}' not found."))
            return

        # ── 1. Revert penalty amounts on obligations ──────────────────────────
        penalized = Obligation.objects.filter(
            organization=org,
            penalty_weeks_applied__gt=0,
        )
        ob_count = 0
        for ob in penalized:
            if ob.original_amount_cents and ob.original_amount_cents != ob.amount_cents:
                msg = (
                    f"  REVERT obligation: {ob.member.get_full_name()} | "
                    f"${ob.amount_cents/100:.2f} → ${ob.original_amount_cents/100:.2f}"
                )
                if dry_run:
                    self.stdout.write(f"  [DRY] {msg}")
                else:
                    with transaction.atomic():
                        ob.amount_cents = ob.original_amount_cents
                        ob.original_amount_cents = None
                        ob.penalty_weeks_applied = 0
                        ob.notes = re.sub(r" \| Late penalty applied[^|]*", "", ob.notes or "")
                        ob.save(update_fields=[
                            "amount_cents", "original_amount_cents",
                            "penalty_weeks_applied", "notes", "updated_at",
                        ])
                    self.stdout.write(msg)
            else:
                # Just clear the counter even if amount wasn't changed
                if not dry_run:
                    ob.penalty_weeks_applied = 0
                    ob.save(update_fields=["penalty_weeks_applied", "updated_at"])
            ob_count += 1

        # ── 2. Reactivate auto-suspended members ──────────────────────────────
        suspended = Member.objects.filter(
            organization=org,
            status=MemberStatus.SUSPENDED,
            notes__contains="Auto-suspended",
        )
        mem_count = 0
        for m in suspended:
            msg = f"  REACTIVATE: {m.get_full_name()}"
            if dry_run:
                self.stdout.write(f"  [DRY] {msg}")
            else:
                with transaction.atomic():
                    m.status = MemberStatus.ACTIVE
                    m.notes = re.sub(
                        r" \| Auto-suspended \d{4}-\d{2}-\d{2}: dues overdue \d+ days\.",
                        "",
                        m.notes or "",
                    )
                    m.save(update_fields=["status", "notes", "updated_at"])
                self.stdout.write(self.style.SUCCESS(msg))
            mem_count += 1

        self.stdout.write(f"\n{'[DRY] ' if dry_run else ''}Done.")
        self.stdout.write(f"  Obligations reverted: {ob_count}")
        self.stdout.write(f"  Members reactivated:  {mem_count}")
