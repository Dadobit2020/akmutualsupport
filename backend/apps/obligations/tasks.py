"""
Celery tasks for obligations: recurring dues generation and reminder dispatch.
"""
import datetime
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_recurring_dues(organization_id: str):
    """
    Create monthly dues obligations for all active members.
    Called by Celery Beat on the 1st of each month.
    Idempotent: skips members who already have a dues obligation for the current month.
    """
    from apps.identity.models import Organization
    from apps.membership.models import Member, MemberStatus
    from apps.obligations.models import Obligation, ObligationStatus, ObligationType
    from apps.ledger.service import post_transaction
    from apps.ledger.models import TransactionSource

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.error(f"Organization {organization_id} not found for dues generation")
        return

    today = datetime.date.today()
    month_start = today.replace(day=1)
    due_date = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)

    # Use a system user — look for the first super-admin
    from apps.identity.models import User, UserOrganizationRole, Role
    system_user = (
        UserOrganizationRole.objects.filter(
            organization=org, role=Role.SUPER_ADMIN, is_active=True
        )
        .select_related("user")
        .values_list("user", flat=True)
        .first()
    )
    if not system_user:
        logger.error(f"No Super Admin found for org {org.slug} — cannot generate dues")
        return
    posted_by = User.objects.get(id=system_user)

    active_members = Member.objects.filter(organization=org, status=MemberStatus.ACTIVE)
    created = 0

    for member in active_members:
        # Idempotency: skip if dues already exist for this month
        already_exists = Obligation.objects.filter(
            organization=org,
            member=member,
            obligation_type=ObligationType.DUES,
            due_date__year=today.year,
            due_date__month=today.month,
        ).exists()
        if already_exists:
            continue

        rule = member.effective_contribution_rule()
        if rule and rule.contribution_type == "exempt":
            continue

        # Default dues amount — configurable per org later (Phase 2)
        dues_amount_cents = 0  # $0 until the org sets a recurring dues amount
        if dues_amount_cents == 0:
            continue

        obligation = Obligation.objects.create(
            organization=org,
            obligation_type=ObligationType.DUES,
            member=member,
            amount_cents=dues_amount_cents,
            due_date=due_date,
            status=ObligationStatus.OPEN,
        )
        post_transaction(
            organization=org,
            description=f"Monthly dues — {member.get_full_name()} — {today.strftime('%B %Y')}",
            transaction_date=today,
            source=TransactionSource.DUES,
            posted_by=posted_by,
            entries=[
                {"account_code": "RECV", "debit_cents": dues_amount_cents, "credit_cents": 0, "member": member, "obligation": obligation},
                {"account_code": "DUES_REV", "debit_cents": 0, "credit_cents": dues_amount_cents, "member": member},
            ],
        )
        created += 1

    logger.info(f"Generated {created} dues obligations for org {org.slug} ({today.strftime('%B %Y')})")


@shared_task
def send_obligation_reminders(organization_id: str):
    """
    Send email reminders for open obligations.
    Cadence: 7 days before due, on the due date, 7/14/30 days overdue.
    Called daily by Celery Beat.
    """
    from apps.identity.models import Organization
    from apps.obligations.models import Obligation, ObligationStatus
    from apps.communications.tasks import queue_email
    from apps.communications.models import MessageTemplate

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        return

    today = datetime.date.today()
    reminder_offsets = [-7, 0, 7, 14, 30]  # days relative to due_date

    open_obligations = Obligation.objects.filter(
        organization=org,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    ).select_related("member", "event")

    # Load templates once
    try:
        template = MessageTemplate.objects.get(organization=org, name="obligation_reminder")
    except MessageTemplate.DoesNotExist:
        template = None

    sent = 0
    for obligation in open_obligations:
        member = obligation.member
        if not member.email:
            continue

        days_diff = (today - obligation.due_date).days  # positive = overdue

        if days_diff not in [abs(o) if o < 0 else -o if o < 0 else o for o in reminder_offsets]:
            # More precisely: is today exactly one of the reminder windows?
            pass

        if days_diff not in reminder_offsets:
            continue

        context = {
            "member_name": member.get_full_name(),
            "amount_due": f"${obligation.outstanding_cents / 100:.2f}",
            "due_date": obligation.due_date.strftime("%B %d, %Y"),
            "event": str(obligation.event) if obligation.event else "recurring dues",
            "days_overdue": max(0, days_diff),
        }

        if days_diff < 0:
            subject = f"Upcoming contribution due in {abs(days_diff)} days — Addis Kidan"
        elif days_diff == 0:
            subject = "Your contribution is due today — Addis Kidan"
        else:
            subject = f"Overdue contribution reminder ({days_diff} days) — Addis Kidan"

        if template:
            _, body = template.render(context, language=member.preferred_language)
        else:
            body = _default_reminder_body(context)

        queue_email(
            organization=org,
            member=member,
            subject=subject,
            body=body,
            template=template,
            obligation=obligation,
        )
        sent += 1

    logger.info(f"Queued {sent} reminder emails for org {org.slug}")


@shared_task
def run_apply_late_penalties():
    """Daily task: apply weekly late penalties and suspend members past 90 days."""
    from django.core.management import call_command
    call_command("apply_late_penalties")


def _default_reminder_body(ctx: dict) -> str:
    return (
        f"Dear {ctx['member_name']},\n\n"
        f"This is a reminder that your contribution of {ctx['amount_due']} "
        f"for {ctx['event']} is due on {ctx['due_date']}.\n\n"
        f"If you have already sent your payment, please disregard this message.\n\n"
        f"Thank you for your continued support of the Addis Kidan Mutual Support Association.\n\n"
        f"— Addis Kidan Administration"
    )
