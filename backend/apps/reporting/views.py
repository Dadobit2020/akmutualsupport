"""
Admin dashboard and reporting views.
"""
import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Q

from apps.identity.permissions import IsAdminRole
from apps.obligations.models import Obligation, ObligationStatus, Payment
from apps.events.models import Event, EventStatus
from apps.reconciliation.models import ImportedTransaction, MatchStatus
from apps.ledger.models import LedgerEntry
from apps.membership.models import Member, MemberStatus


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def dashboard(request):
    """One-screen financial overview for Treasurer / Chairperson."""
    org = getattr(request, "organization", None)

    outstanding = Obligation.objects.filter(
        organization=org,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    ).aggregate(total=Sum("amount_cents") - Sum("paid_cents"))["total"] or 0

    active_events = Event.objects.filter(
        organization=org,
        status__in=[EventStatus.OBLIGATIONS_GENERATED, EventStatus.COLLECTING],
    ).count()

    pending_approval = Event.objects.filter(
        organization=org, status=EventStatus.PENDING_APPROVAL
    ).count()

    review_queue_count = ImportedTransaction.objects.filter(
        organization=org,
        match_status__in=[MatchStatus.UNMATCHED, MatchStatus.AUTO_MATCHED],
    ).exclude(match_status=MatchStatus.APPLIED).count()

    recent_payments = Payment.objects.filter(
        organization=org,
        payment_date__gte=datetime.date.today() - datetime.timedelta(days=30),
    ).aggregate(total=Sum("amount_cents"))["total"] or 0

    active_members = Member.objects.filter(
        organization=org, status=MemberStatus.ACTIVE
    ).count()

    return Response({
        "outstanding_cents": outstanding,
        "active_events": active_events,
        "pending_approval_events": pending_approval,
        "reconciliation_review_queue": review_queue_count,
        "payments_last_30_days_cents": recent_payments,
        "active_members": active_members,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def outstanding_balances(request):
    """Per-member outstanding balance list."""
    org = getattr(request, "organization", None)

    data = (
        Obligation.objects.filter(
            organization=org,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        )
        .values("member__id", "member__first_name", "member__last_name", "member__email")
        .annotate(
            total_owed=Sum("amount_cents"),
            total_paid=Sum("paid_cents"),
        )
        .order_by("-total_owed")
    )

    result = [
        {
            "member_id": row["member__id"],
            "member_name": f"{row['member__first_name']} {row['member__last_name']}",
            "email": row["member__email"],
            "total_owed_cents": row["total_owed"],
            "total_paid_cents": row["total_paid"],
            "outstanding_cents": (row["total_owed"] or 0) - (row["total_paid"] or 0),
        }
        for row in data
    ]

    return Response(result)
