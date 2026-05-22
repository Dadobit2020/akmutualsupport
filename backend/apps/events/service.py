"""
Event service — manages the event lifecycle and triggers obligation generation.
"""
import datetime
from django.db import transaction as db_transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Event, EventStatus
from apps.obligations.models import Obligation, ObligationStatus
from apps.ledger.service import post_transaction
from apps.ledger.models import TransactionSource
from apps.membership.models import Member, MemberStatus


def submit_event_for_approval(event: Event, submitted_by) -> Event:
    if event.status != EventStatus.DRAFT:
        raise ValidationError("Only draft events can be submitted for approval.")
    event.status = EventStatus.PENDING_APPROVAL
    event.submitted_by = submitted_by
    event.submitted_at = timezone.now()
    event.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
    return event


def approve_event(event: Event, approved_by) -> Event:
    if event.status != EventStatus.PENDING_APPROVAL:
        raise ValidationError("Only pending-approval events can be approved.")

    with db_transaction.atomic():
        event.status = EventStatus.APPROVED
        event.approved_by = approved_by
        event.approved_at = timezone.now()

        # Set contribution deadline from org config
        deadline_days = event.organization.contribution_deadline_days
        event.contribution_deadline = datetime.date.today() + datetime.timedelta(days=deadline_days)
        event.save(update_fields=["status", "approved_by", "approved_at", "contribution_deadline", "updated_at"])

        _generate_obligations(event, posted_by=approved_by)

        event.status = EventStatus.OBLIGATIONS_GENERATED
        event.save(update_fields=["status", "updated_at"])

    return event


def reject_event(event: Event, rejected_by, reason: str) -> Event:
    if event.status != EventStatus.PENDING_APPROVAL:
        raise ValidationError("Only pending-approval events can be rejected.")
    event.status = EventStatus.REJECTED
    event.rejection_reason = reason
    event.save(update_fields=["status", "rejection_reason", "updated_at"])
    return event


def reverse_event(event: Event, reversed_by, reason: str) -> Event:
    """
    Reverse an approved event by posting compensating ledger entries.
    The event record is preserved; its status becomes REVERSED.
    """
    if not event.is_reversible:
        raise ValidationError(f"Event in status '{event.status}' cannot be reversed.")
    if not reason.strip():
        raise ValidationError("A reason is required for event reversals.")

    with db_transaction.atomic():
        # Reverse each ledger transaction belonging to this event
        from apps.ledger.service import post_reversal
        txns = event.ledger_transactions.exclude(source=TransactionSource.REVERSAL)
        for txn in txns:
            if not hasattr(txn, "reversed_by"):
                post_reversal(original_txn=txn, posted_by=reversed_by, reason=reason)

        # Cancel open obligations
        Obligation.objects.filter(event=event, status__in=[
            ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID
        ]).update(status=ObligationStatus.CANCELLED, updated_at=timezone.now())

        event.status = EventStatus.REVERSED
        event.save(update_fields=["status", "updated_at"])

    return event


def _generate_obligations(event: Event, posted_by):
    """
    For each active, non-exempt member (excluding the affected household),
    create an Obligation and post the corresponding ledger entries.
    """
    affected_household = event.affected_household
    eligible_members = Member.objects.filter(
        organization=event.organization,
        status=MemberStatus.ACTIVE,
    ).select_related("contribution_rule", "household")

    obligations_to_create = []
    ledger_entries = []

    for member in eligible_members:
        rule = member.effective_contribution_rule()

        # Auto-waive for the affected household
        if member.household_id == affected_household.id:
            obligations_to_create.append(Obligation(
                organization=event.organization,
                event=event,
                member=member,
                amount_cents=0,
                due_date=event.contribution_deadline,
                status=ObligationStatus.WAIVED,
                waiver_reason="Affected household — auto-waived",
            ))
            continue

        if rule is None:
            # Default to full contribution
            amount_cents = event.payout_amount_cents // max(1, eligible_members.count())
        else:
            per_member_share = event.payout_amount_cents // max(1, eligible_members.count())
            amount_cents = rule.calculate_obligation_cents(per_member_share)

        if amount_cents == 0:
            obligations_to_create.append(Obligation(
                organization=event.organization,
                event=event,
                member=member,
                amount_cents=0,
                due_date=event.contribution_deadline,
                status=ObligationStatus.WAIVED,
                waiver_reason="Exempt contribution rule",
            ))
            continue

        obligations_to_create.append(Obligation(
            organization=event.organization,
            event=event,
            member=member,
            amount_cents=amount_cents,
            due_date=event.contribution_deadline,
            status=ObligationStatus.OPEN,
        ))

    created_obligations = Obligation.objects.bulk_create(obligations_to_create)

    # Post ledger entries: DR Member Receivables / CR Event Payout Expense per member
    for obligation in created_obligations:
        if obligation.amount_cents > 0:
            post_transaction(
                organization=event.organization,
                description=f"Obligation for {obligation.member.get_full_name()} — {event}",
                transaction_date=datetime.date.today(),
                source=TransactionSource.EVENT_OBLIGATION,
                posted_by=posted_by,
                event=event,
                entries=[
                    {
                        "account_code": "RECV",
                        "debit_cents": obligation.amount_cents,
                        "credit_cents": 0,
                        "description": f"Receivable from {obligation.member.get_full_name()}",
                        "member": obligation.member,
                        "obligation": obligation,
                    },
                    {
                        "account_code": "PAYOUT_EXP",
                        "debit_cents": 0,
                        "credit_cents": obligation.amount_cents,
                        "description": f"Event payout share for {event}",
                        "member": obligation.member,
                        "obligation": obligation,
                    },
                ],
            )
