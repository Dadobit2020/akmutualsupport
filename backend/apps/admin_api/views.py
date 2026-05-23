"""
Admin API views — full control panel endpoints.
All views require IsAuthenticated + IsOrgAdmin.
"""
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.identity.models import UserOrganizationRole
from apps.membership.models import Member, MemberStatus, MembershipTier
from apps.obligations.models import Obligation, ObligationStatus, Payment
from apps.ledger.models import (
    LedgerTransaction,
    LedgerEntry,
    LedgerAccount,
    TransactionSource,
)
from apps.events.models import Event, EventType, EventStatus
from apps.membership.models import Household

from .permissions import IsOrgAdmin

_ADMIN_PERMISSIONS = [IsAuthenticated, IsOrgAdmin]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paginate(queryset, request, page_size=20):
    """Simple manual pagination returning (items, total, page, total_pages)."""
    try:
        page = int(request.query_params.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    page = max(1, page)
    total = queryset.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return list(queryset[start:end]), total, page, total_pages


def _serialize_payment(p):
    return {
        "id": str(p.id),
        "member_id": str(p.member_id) if p.member_id else None,
        "member_name": p.member.get_full_name() if p.member else "—",
        "amount_cents": p.amount_cents,
        "payment_date": str(p.payment_date),
        "method": p.method,
        "reference": p.reference,
        "notes": p.notes,
    }


def _serialize_member_brief(m):
    total_paid = m.payments.aggregate(s=Sum("amount_cents"))["s"] or 0
    outstanding = m.obligations.filter(
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID]
    ).aggregate(s=Sum("amount_cents") - Sum("paid_cents"))["s"] or 0
    # aggregate subtraction can return None per row — recalculate safely
    open_obs = m.obligations.filter(
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID]
    )
    outstanding_cents = sum(o.outstanding_cents for o in open_obs)
    return {
        "id": str(m.id),
        "first_name": m.first_name,
        "last_name": m.last_name,
        "email": m.email,
        "phone": m.phone,
        "join_date": str(m.join_date),
        "status": m.status,
        "tier": m.tier,
        "total_paid_cents": total_paid,
        "outstanding_cents": outstanding_cents,
    }


def _serialize_obligation(o):
    return {
        "id": str(o.id),
        "obligation_type": o.obligation_type,
        "member_id": str(o.member_id),
        "member_name": o.member.get_full_name(),
        "amount_cents": o.amount_cents,
        "paid_cents": o.paid_cents,
        "outstanding_cents": o.outstanding_cents,
        "due_date": str(o.due_date),
        "status": o.status,
        "event_id": str(o.event_id) if o.event_id else None,
    }


def _serialize_event(e):
    return {
        "id": str(e.id),
        "event_type": e.event_type,
        "household": str(e.affected_household),
        "household_id": str(e.affected_household_id),
        "event_date": str(e.event_date),
        "description": e.description,
        "payout_amount_cents": e.payout_amount_cents,
        "status": e.status,
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def dashboard(request):
    org = request.organization

    members_qs = Member.objects.filter(organization=org)
    total_members = members_qs.count()
    active_members = members_qs.filter(status=MemberStatus.ACTIVE).count()

    # New this month
    today = timezone.localdate()
    members_this_month = members_qs.filter(
        join_date__year=today.year,
        join_date__month=today.month,
    ).count()

    # Cash / revenue ledger totals via LedgerEntry
    try:
        cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
        total_collected_cents = (
            LedgerEntry.objects.filter(account=cash_account, debit_cents__gt=0)
            .aggregate(s=Sum("debit_cents"))["s"] or 0
        )
    except LedgerAccount.DoesNotExist:
        total_collected_cents = Payment.objects.filter(
            organization=org
        ).aggregate(s=Sum("amount_cents"))["s"] or 0

    try:
        payout_account = LedgerAccount.objects.get(organization=org, code="PAYOUT_EXP")
        total_payouts_cents = (
            LedgerEntry.objects.filter(account=payout_account, debit_cents__gt=0)
            .aggregate(s=Sum("debit_cents"))["s"] or 0
        )
    except LedgerAccount.DoesNotExist:
        total_payouts_cents = 0

    # Outstanding obligations
    open_obs = Obligation.objects.filter(
        organization=org,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    )
    outstanding_cents = sum(o.outstanding_cents for o in open_obs)

    # Obligations by status
    from django.db.models import Count
    obs_by_status_qs = (
        Obligation.objects.filter(organization=org)
        .values("status")
        .annotate(count=Count("id"))
    )
    obligations_by_status = {row["status"]: row["count"] for row in obs_by_status_qs}

    # Recent payments
    recent_payments_qs = (
        Payment.objects.filter(organization=org)
        .select_related("member")
        .order_by("-payment_date", "-created_at")[:10]
    )
    recent_payments = [_serialize_payment(p) for p in recent_payments_qs]

    return Response({
        "total_members": total_members,
        "active_members": active_members,
        "total_collected_cents": total_collected_cents,
        "total_payouts_cents": total_payouts_cents,
        "outstanding_cents": outstanding_cents,
        "members_this_month": members_this_month,
        "recent_payments": recent_payments,
        "obligations_by_status": obligations_by_status,
    })


# ── Members ───────────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def members_list(request):
    org = request.organization

    if request.method == "GET":
        qs = Member.objects.filter(organization=org).order_by("last_name", "first_name")

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        items, total, page, total_pages = _paginate(qs, request, page_size=20)
        return Response({
            "count": total,
            "page": page,
            "total_pages": total_pages,
            "results": [_serialize_member_brief(m) for m in items],
        })

    # POST — create member
    data = request.data
    required = ["first_name", "last_name", "join_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response(
            {"detail": f"Missing required fields: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    member = Member.objects.create(
        organization=org,
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data.get("email", "").strip(),
        phone=data.get("phone", "").strip(),
        join_date=data["join_date"],
        status=data.get("status", MemberStatus.ACTIVE),
        tier=data.get("tier", MembershipTier.STANDARD),
        notes=data.get("notes", ""),
    )
    return Response(_serialize_member_brief(member), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes(_ADMIN_PERMISSIONS)
def member_detail(request, member_id):
    org = request.organization
    try:
        member = Member.objects.get(id=member_id, organization=org)
    except Member.DoesNotExist:
        return Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        # Obligations
        obligations = list(
            Obligation.objects.filter(member=member).order_by("-due_date")
        )
        # Payments
        payments = list(
            Payment.objects.filter(member=member).order_by("-payment_date")
        )
        data = _serialize_member_brief(member)
        data["notes"] = member.notes
        data["address"] = member.address
        data["phone_whatsapp"] = member.phone_whatsapp
        data["obligations"] = [_serialize_obligation(o) for o in obligations]
        data["payments"] = [_serialize_payment(p) for p in payments]
        return Response(data)

    # PATCH — update member
    allowed = ["status", "tier", "email", "phone", "phone_whatsapp", "notes", "address", "first_name", "last_name"]
    for field in allowed:
        if field in request.data:
            setattr(member, field, request.data[field])
    member.save()
    return Response(_serialize_member_brief(member))


# ── Payments ──────────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def payments_list(request):
    org = request.organization

    if request.method == "GET":
        qs = (
            Payment.objects.filter(organization=org)
            .select_related("member")
            .order_by("-payment_date", "-created_at")
        )

        member_id = request.query_params.get("member", "").strip()
        if member_id:
            qs = qs.filter(member_id=member_id)

        method = request.query_params.get("method", "").strip()
        if method:
            qs = qs.filter(method=method)

        date_from = request.query_params.get("date_from", "").strip()
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)

        date_to = request.query_params.get("date_to", "").strip()
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)

        items, total, page, total_pages = _paginate(qs, request, page_size=20)
        return Response({
            "count": total,
            "page": page,
            "total_pages": total_pages,
            "results": [_serialize_payment(p) for p in items],
        })

    # POST — record payment
    data = request.data
    required = ["member_id", "amount_cents", "payment_date", "method"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response(
            {"detail": f"Missing required fields: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        member = Member.objects.get(id=data["member_id"], organization=org)
    except Member.DoesNotExist:
        return Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)

    amount_cents = int(data["amount_cents"])
    if amount_cents <= 0:
        return Response(
            {"detail": "amount_cents must be positive."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        # Get ledger accounts
        try:
            cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
            contrib_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
        except LedgerAccount.DoesNotExist as exc:
            return Response(
                {"detail": f"Ledger account not found: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Create ledger transaction
        ledger_tx = LedgerTransaction.objects.create(
            organization=org,
            description=f"Payment from {member.get_full_name()} — {data.get('reference', '')}".strip(" —"),
            transaction_date=data["payment_date"],
            source=TransactionSource.PAYMENT,
            posted_by=request.user,
            notes=data.get("notes", ""),
        )

        # DR CASH
        LedgerEntry.objects.create(
            ledger_transaction=ledger_tx,
            account=cash_account,
            debit_cents=amount_cents,
            credit_cents=0,
            member=member,
            description=f"Cash receipt from {member.get_full_name()}",
        )
        # CR CONTRIB_REV
        LedgerEntry.objects.create(
            ledger_transaction=ledger_tx,
            account=contrib_account,
            debit_cents=0,
            credit_cents=amount_cents,
            member=member,
            description=f"Contribution revenue from {member.get_full_name()}",
        )

        # Create payment record
        payment = Payment.objects.create(
            organization=org,
            member=member,
            amount_cents=amount_cents,
            payment_date=data["payment_date"],
            method=data["method"],
            reference=data.get("reference", ""),
            notes=data.get("notes", ""),
            ledger_transaction=ledger_tx,
        )

        # Apply to open obligations (oldest first) — auto-apply up to amount
        remaining = amount_cents
        open_obs = Obligation.objects.filter(
            member=member,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        ).order_by("due_date")
        for ob in open_obs:
            if remaining <= 0:
                break
            apply = min(remaining, ob.outstanding_cents)
            if apply > 0:
                ob.apply_payment_cents(apply)
                remaining -= apply

    return Response(_serialize_payment(payment), status=status.HTTP_201_CREATED)


# ── Obligations ───────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def obligations_list(request):
    org = request.organization
    qs = (
        Obligation.objects.filter(organization=org)
        .select_related("member")
        .order_by("due_date")
    )

    status_filter = request.query_params.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    member_id = request.query_params.get("member", "").strip()
    if member_id:
        qs = qs.filter(member_id=member_id)

    sort = request.query_params.get("sort", "due_date").strip()
    if sort in ("due_date", "-due_date", "amount_cents", "-amount_cents"):
        qs = qs.order_by(sort)

    items, total, page, total_pages = _paginate(qs, request, page_size=20)
    return Response({
        "count": total,
        "page": page,
        "total_pages": total_pages,
        "results": [_serialize_obligation(o) for o in items],
    })


@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def send_reminders(request):
    """
    Enqueue reminder communications for all open/partially-paid obligations
    that have a member with a valid email or phone.
    """
    from apps.communications.tasks import queue_email, queue_sms

    org = request.organization
    open_obs = (
        Obligation.objects.filter(
            organization=org,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        )
        .select_related("member")
    )

    queued = 0
    for ob in open_obs:
        m = ob.member
        if not m:
            continue
        outstanding = ob.outstanding_cents
        due_str = str(ob.due_date)
        subject = f"AKMSA: Contribution reminder — {outstanding / 100:.2f} USD due {due_str}"
        body = (
            f"Dear {m.first_name},\n\n"
            f"This is a reminder that your contribution of ${outstanding / 100:.2f} "
            f"is due on {due_str}.\n\n"
            f"Please contact your association treasurer to arrange payment.\n\n"
            f"Thank you,\nAddis Kidan Mutual Support Association"
        )
        if m.email:
            queue_email(
                organization=org,
                member=m,
                recipient_address=m.email,
                subject=subject,
                body=body,
                obligation=ob,
            )
            queued += 1
        elif m.phone:
            queue_sms(
                organization=org,
                member=m,
                recipient_phone=m.phone,
                body=body,
                obligation=ob,
            )
            queued += 1

    return Response({"queued": queued, "detail": f"Reminders enqueued for {queued} obligation(s)."})


# ── Events ────────────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def events_list(request):
    org = request.organization

    if request.method == "GET":
        qs = Event.objects.filter(organization=org).order_by("-event_date")
        items, total, page, total_pages = _paginate(qs, request, page_size=20)
        return Response({
            "count": total,
            "page": page,
            "total_pages": total_pages,
            "results": [_serialize_event(e) for e in items],
        })

    # POST — create event
    data = request.data
    required = ["event_type", "household_name", "event_date", "payout_amount_cents"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response(
            {"detail": f"Missing required fields: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if data["event_type"] not in [c[0] for c in EventType.choices]:
        return Response(
            {"detail": f"Invalid event_type. Choices: {[c[0] for c in EventType.choices]}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        # Get or create household by name
        household, _ = Household.objects.get_or_create(
            organization=org,
            name=data["household_name"].strip(),
        )

        event = Event.objects.create(
            organization=org,
            event_type=data["event_type"],
            affected_household=household,
            event_date=data["event_date"],
            description=data.get("description", "").strip(),
            payout_amount_cents=int(data["payout_amount_cents"]),
            status=EventStatus.DRAFT,
            submitted_by=request.user,
        )

    return Response(_serialize_event(event), status=status.HTTP_201_CREATED)
