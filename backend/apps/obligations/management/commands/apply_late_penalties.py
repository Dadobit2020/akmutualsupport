"""
Management command: apply_late_penalties

Runs daily (via Celery beat). For every OPEN or PARTIALLY_PAID DUES obligation
that is past its due_date:

  - Adds 15% of the original amount per full week overdue (non-compounding).
  - After `suspension_after_days` days overdue (default 90), suspends the member.

Usage:
    python manage.py apply_late_penalties [--dry-run] [--org-slug addis-kidan]
"""
import math
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Apply weekly late penalties to overdue DUES obligations and suspend members past 90 days."

    def add_arguments(self, parser):
        parser.add_argument("--org-slug", default="addis-kidan")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.obligations.models import Obligation, ObligationStatus, ObligationType
        from apps.membership.models import MemberStatus
        from apps.admin_api.models import OrgSettings

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        try:
            org = Organization.objects.get(slug=options["org_slug"])
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Organization '{options['org_slug']}' not found."))
            return

        settings, _ = OrgSettings.objects.get_or_create(organization=org)
        penalty_pct = settings.late_penalty_pct      # e.g. 15
        suspend_days = settings.suspension_after_days  # e.g. 90

        today = date.today()
        stats = {"penalties_added": 0, "suspended": 0, "skipped": 0}

        overdue = Obligation.objects.filter(
            organization=org,
            obligation_type=ObligationType.DUES,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
            due_date__lt=today,
        ).select_related("member")

        for ob in overdue:
            days_overdue = (today - ob.due_date).days
            weeks_overdue = days_overdue // 7

            # Initialise original amount on first penalty encounter
            base = ob.original_amount_cents or ob.amount_cents

            new_penalty_weeks = weeks_overdue - ob.penalty_weeks_applied
            if new_penalty_weeks > 0:
                penalty_per_week = math.ceil(base * penalty_pct / 100)
                penalty_total = penalty_per_week * new_penalty_weeks
                msg = (
                    f"  PENALTY: {ob.member.get_full_name()} | "
                    f"due {ob.due_date} | {days_overdue}d overdue | "
                    f"+{new_penalty_weeks}wk × {penalty_pct}% = +${penalty_total/100:.2f}"
                )
                if dry_run:
                    self.stdout.write(f"  [DRY] {msg}")
                else:
                    with transaction.atomic():
                        ob.original_amount_cents = base
                        ob.amount_cents += penalty_total
                        ob.penalty_weeks_applied = weeks_overdue
                        ob.notes = (ob.notes or "") + (
                            f" | Late penalty applied {today}: "
                            f"+{new_penalty_weeks} week(s) × {penalty_pct}% = +${penalty_total/100:.2f}"
                        )
                        ob.save(update_fields=[
                            "original_amount_cents", "amount_cents",
                            "penalty_weeks_applied", "notes", "updated_at",
                        ])
                    self.stdout.write(self.style.WARNING(msg))
                stats["penalties_added"] += 1
            else:
                stats["skipped"] += 1

            # Suspension check — only suspend if the penalty system has been
            # actively running for at least 12 weeks on this obligation.
            # This prevents suspending everyone the first time the command runs
            # on obligations that were already old when the feature was deployed.
            weeks_of_penalty = ob.penalty_weeks_applied  # updated above
            if days_overdue >= suspend_days and weeks_of_penalty >= 12:
                member = ob.member
                if member.status not in (MemberStatus.SUSPENDED, MemberStatus.LEFT, MemberStatus.DECEASED):
                    suspend_msg = (
                        f"  SUSPEND: {member.get_full_name()} — "
                        f"{days_overdue}d overdue on obligation due {ob.due_date}"
                    )
                    if dry_run:
                        self.stdout.write(f"  [DRY] {suspend_msg}")
                    else:
                        member.status = MemberStatus.SUSPENDED
                        member.notes = (member.notes or "") + (
                            f" | Auto-suspended {today}: dues overdue {days_overdue} days."
                        )
                        member.save(update_fields=["status", "notes", "updated_at"])
                        self.stdout.write(self.style.ERROR(suspend_msg))
                    stats["suspended"] += 1

        self.stdout.write("\n" + "=" * 55)
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style(
            f"{'DRY RUN ' if dry_run else ''}Complete.\n"
            f"  Penalties applied: {stats['penalties_added']}\n"
            f"  Members suspended: {stats['suspended']}\n"
            f"  Already up-to-date: {stats['skipped']}"
        ))
