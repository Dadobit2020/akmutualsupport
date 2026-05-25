"""
Admin API views — full control panel endpoints.
All views require IsAuthenticated + IsOrgAdmin.
"""
import math
from datetime import date, timedelta

from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.identity.models import UserOrganizationRole
from apps.membership.models import Member, MemberStatus, MembershipTier
from apps.obligations.models import Obligation, ObligationStatus, ObligationType, Payment
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


# ── Audit helper ──────────────────────────────────────────────────────────────

def log_action(request, action: str, description: str,
               target_type: str = "", target_id: str = "", target_label: str = ""):
    from .models import AdminActionLog
    AdminActionLog.objects.create(
        organization=request.organization,
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        target_label=target_label,
        description=description,
    )


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
        "penalty_weeks_applied": o.penalty_weeks_applied,
        "original_amount_cents": o.original_amount_cents,
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


def _serialize_family_member(fm):
    return {
        "id": str(fm.id),
        "first_name": fm.first_name,
        "last_name": fm.last_name,
        "first_name_am": fm.first_name_am,
        "last_name_am": fm.last_name_am,
        "relationship": fm.relationship,
        "date_of_birth": str(fm.date_of_birth),
        "gender": fm.gender,
        "age": fm.age,
        "is_active": fm.is_active,
        "notes": fm.notes,
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
    log_action(
        request, "member_created",
        f"Added new member: {member.get_full_name()}",
        target_type="Member", target_id=str(member.id), target_label=member.get_full_name(),
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
        from apps.membership.models import FamilyMember
        obligations = list(Obligation.objects.filter(member=member).order_by("-due_date"))
        payments = list(Payment.objects.filter(member=member).order_by("-payment_date"))
        family = list(FamilyMember.objects.filter(member=member))
        data = _serialize_member_brief(member)
        data["notes"] = member.notes
        data["address"] = member.address
        data["phone_whatsapp"] = member.phone_whatsapp
        data["obligations"] = [_serialize_obligation(o) for o in obligations]
        data["payments"] = [_serialize_payment(p) for p in payments]
        data["family_members"] = [_serialize_family_member(fm) for fm in family]
        return Response(data)

    # PATCH — update member
    allowed = ["status", "tier", "email", "phone", "phone_whatsapp", "notes", "address", "first_name", "last_name"]
    old_status = member.status
    for field in allowed:
        if field in request.data:
            setattr(member, field, request.data[field])
    member.save()

    # Log status changes specifically
    new_status = member.status
    if "status" in request.data and old_status != new_status:
        action_map = {
            "suspended": "member_suspended",
            "active": "member_activated",
            "inactive": "member_deactivated",
            "left": "member_left",
        }
        action = action_map.get(new_status, "member_status_changed")
        log_action(
            request, action,
            f"Changed {member.get_full_name()} status: {old_status} → {new_status}",
            target_type="Member", target_id=str(member.id), target_label=member.get_full_name(),
        )
    elif any(f in request.data for f in ["email", "phone", "notes", "address", "first_name", "last_name", "tier"]):
        changed = [f for f in allowed if f in request.data and f != "status"]
        log_action(
            request, "member_updated",
            f"Updated {member.get_full_name()} — fields: {', '.join(changed)}",
            target_type="Member", target_id=str(member.id), target_label=member.get_full_name(),
        )
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

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                models.Q(member__first_name__icontains=search) |
                models.Q(member__last_name__icontains=search) |
                models.Q(member__email__icontains=search)
            )

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

    log_action(
        request, "payment_recorded",
        f"Recorded ${amount_cents/100:.2f} payment from {member.get_full_name()} on {data['payment_date']}",
        target_type="Payment", target_id=str(payment.id),
        target_label=member.get_full_name(),
    )
    return Response(_serialize_payment(payment), status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes(_ADMIN_PERMISSIONS)
def payment_detail(request, payment_id):
    """Void a payment: reverse ledger entries, unapply from obligations, delete record."""
    org = request.organization
    try:
        payment = Payment.objects.select_related("member", "ledger_transaction").get(
            id=payment_id, organization=org
        )
    except Payment.DoesNotExist:
        return Response({"detail": "Payment not found."}, status=404)

    member_name = payment.member.get_full_name() if payment.member else "—"
    amount_cents = payment.amount_cents
    pay_date = str(payment.payment_date)

    with transaction.atomic():
        # Reverse obligation applications — add back paid_cents
        from apps.obligations.models import PaymentApplication
        for app in payment.applications.select_related("obligation").all():
            ob = app.obligation
            ob.paid_cents = max(0, ob.paid_cents - app.applied_cents)
            if ob.paid_cents == 0:
                ob.status = ObligationStatus.OPEN
            elif ob.paid_cents < ob.amount_cents:
                ob.status = ObligationStatus.PARTIALLY_PAID
            ob.save(update_fields=["paid_cents", "status", "updated_at"])

        # Reverse ledger entries by creating a negating transaction
        if payment.ledger_transaction:
            orig = payment.ledger_transaction
            try:
                cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
                contrib_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
                rev_txn = LedgerTransaction.objects.create(
                    organization=org,
                    description=f"VOID — {orig.description}",
                    transaction_date=date.today(),
                    source=TransactionSource.ADJUSTMENT,
                    posted_by=request.user,
                    notes=f"Reversal of payment {payment_id} recorded on {pay_date}",
                )
                LedgerEntry.objects.create(
                    ledger_transaction=rev_txn, account=contrib_account,
                    debit_cents=amount_cents, credit_cents=0,
                    member=payment.member, description="Reversal — void payment",
                )
                LedgerEntry.objects.create(
                    ledger_transaction=rev_txn, account=cash_account,
                    debit_cents=0, credit_cents=amount_cents,
                    member=payment.member, description="Reversal — void payment",
                )
            except LedgerAccount.DoesNotExist:
                pass  # Still delete the payment even if ledger accounts aren't found

        payment.delete()

    log_action(
        request, "payment_deleted",
        f"Deleted ${amount_cents/100:.2f} payment from {member_name} dated {pay_date}",
        target_type="Payment", target_id=str(payment_id), target_label=member_name,
    )
    return Response(status=204)


# ── Activity Log ──────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def activity_log(request):
    from .models import AdminActionLog
    org = request.organization
    qs = AdminActionLog.objects.filter(organization=org).select_related("actor")
    action_filter = request.query_params.get("action", "").strip()
    if action_filter:
        qs = qs.filter(action=action_filter)
    items, total, page, total_pages = _paginate(qs, request, page_size=50)
    return Response({
        "count": total,
        "page": page,
        "total_pages": total_pages,
        "results": [
            {
                "id": item.id,
                "action": item.action,
                "actor": item.actor.get_full_name() if item.actor else "System",
                "actor_email": item.actor.email if item.actor else "",
                "target_type": item.target_type,
                "target_label": item.target_label,
                "description": item.description,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
    })


# ── Obligations ───────────────────────────────────────────────────────────────

@api_view(["PATCH", "DELETE"])
@permission_classes(_ADMIN_PERMISSIONS)
def obligation_detail(request, obligation_id):
    org = request.organization
    try:
        ob = Obligation.objects.select_related("member").get(id=obligation_id, organization=org)
    except Obligation.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    if request.method == "DELETE":
        if ob.paid_cents > 0:
            return Response(
                {"detail": "Cannot delete an obligation that has payments applied. Cancel it instead."},
                status=400,
            )
        ob.delete()
        return Response(status=204)

    # PATCH — editable fields: amount_cents, due_date, status, notes
    data = request.data
    changed = []

    if "amount_cents" in data:
        new_amount = int(data["amount_cents"])
        if new_amount < ob.paid_cents:
            return Response(
                {"detail": "Amount cannot be less than what has already been paid."},
                status=400,
            )
        ob.amount_cents = new_amount
        changed.append("amount_cents")

    if "due_date" in data:
        from datetime import date as _date
        try:
            ob.due_date = _date.fromisoformat(data["due_date"])
            changed.append("due_date")
        except ValueError:
            return Response({"detail": "Invalid due_date format (use YYYY-MM-DD)."}, status=400)

    if "status" in data:
        allowed = [ObligationStatus.WAIVED, ObligationStatus.CANCELLED,
                   ObligationStatus.OPEN, ObligationStatus.WRITTEN_OFF]
        if data["status"] not in allowed:
            return Response(
                {"detail": f"Status must be one of: {[s for s in allowed]}."},
                status=400,
            )
        ob.status = data["status"]
        changed.append("status")

    if "notes" in data:
        ob.notes = data["notes"]
        changed.append("notes")

    if changed:
        ob.save(update_fields=changed + ["updated_at"])

    return Response(_serialize_obligation(ob))


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

    from django.db.models import Sum, F, ExpressionWrapper, IntegerField
    total_outstanding = qs.aggregate(
        s=Sum(
            ExpressionWrapper(F("amount_cents") - F("paid_cents"), output_field=IntegerField())
        )
    )["s"] or 0

    items, total, page, total_pages = _paginate(qs, request, page_size=20)
    return Response({
        "count": total,
        "page": page,
        "total_pages": total_pages,
        "total_outstanding_cents": total_outstanding,
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


# ── Settings ──────────────────────────────────────────────────────────────────

@api_view(["GET", "PATCH"])
@permission_classes(_ADMIN_PERMISSIONS)
def org_settings(request):
    from .models import OrgSettings, SettingsAuditLog
    org = request.organization
    settings_obj, _ = OrgSettings.objects.get_or_create(organization=org)

    if request.method == "GET":
        active_count = Member.objects.filter(organization=org, status=MemberStatus.ACTIVE).count()
        audit_logs = SettingsAuditLog.objects.filter(organization=org).select_related("changed_by")[:20]
        return Response({
            "entrance_fee_cents": settings_obj.entrance_fee_cents,
            "maintenance_fee_cents": settings_obj.maintenance_fee_cents,
            "maintenance_fee_anchor_month": settings_obj.maintenance_fee_anchor_month,
            "assessment_due_days": settings_obj.assessment_due_days,
            "late_penalty_pct": settings_obj.late_penalty_pct,
            "suspension_after_days": settings_obj.suspension_after_days,
            "active_member_count": active_count,
            "audit_log": [
                {
                    "field": log.field_name,
                    "old_value": log.old_value,
                    "new_value": log.new_value,
                    "changed_by": log.changed_by.get_full_name() if log.changed_by else "—",
                    "changed_at": log.changed_at.isoformat(),
                }
                for log in audit_logs
            ],
        })

    # PATCH — update with audit logging
    UPDATABLE = {
        "entrance_fee_cents": int,
        "maintenance_fee_cents": int,
        "maintenance_fee_anchor_month": int,
        "assessment_due_days": int,
        "late_penalty_pct": int,
        "suspension_after_days": int,
    }
    logs = []
    errors = {}
    for field, cast in UPDATABLE.items():
        if field not in request.data:
            continue
        try:
            new_val = cast(request.data[field])
        except (ValueError, TypeError):
            errors[field] = "Must be an integer."
            continue
        if field == "maintenance_fee_anchor_month" and not (1 <= new_val <= 12):
            errors[field] = "Must be 1–12."
            continue
        old_val = getattr(settings_obj, field)
        if old_val != new_val:
            logs.append(SettingsAuditLog(
                organization=org,
                changed_by=request.user,
                field_name=field,
                old_value=str(old_val),
                new_value=str(new_val),
            ))
            setattr(settings_obj, field, new_val)

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    settings_obj.updated_by = request.user
    settings_obj.save()
    if logs:
        SettingsAuditLog.objects.bulk_create(logs)

    return Response({"ok": True})


# ── Assessment calculator ──────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def assessment_preview(request):
    """Return per-member fee for a given total payout (without creating anything)."""
    from .models import OrgSettings
    org = request.organization
    try:
        total_cents = round(float(request.query_params.get("amount", 0)) * 100)
    except (ValueError, TypeError):
        return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
    if total_cents <= 0:
        return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

    active_count = Member.objects.filter(organization=org, status=MemberStatus.ACTIVE).count()
    if active_count == 0:
        return Response({"error": "No active members found."}, status=status.HTTP_400_BAD_REQUEST)

    per_member_cents = math.ceil(total_cents / active_count)
    settings_obj, _ = OrgSettings.objects.get_or_create(organization=org)
    return Response({
        "total_payout_cents": total_cents,
        "active_member_count": active_count,
        "per_member_cents": per_member_cents,
        "due_date": str(date.today() + timedelta(days=settings_obj.assessment_due_days)),
    })


@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def process_assessment(request):
    """Bulk-create obligations for all active members for a special assessment."""
    from .models import OrgSettings
    org = request.organization

    try:
        total_cents = int(request.data.get("total_cents", 0))
        per_member_cents = int(request.data.get("per_member_cents", 0))
        due_date_str = request.data.get("due_date", "")
        description = request.data.get("description", "Special Assessment").strip() or "Special Assessment"
    except (ValueError, TypeError):
        return Response({"error": "Invalid data."}, status=status.HTTP_400_BAD_REQUEST)

    if total_cents <= 0 or per_member_cents <= 0:
        return Response({"error": "Amounts must be positive."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        due_date = date.fromisoformat(due_date_str)
    except (ValueError, TypeError):
        settings_obj, _ = OrgSettings.objects.get_or_create(organization=org)
        due_date = date.today() + timedelta(days=settings_obj.assessment_due_days)

    active_members = list(Member.objects.filter(organization=org, status=MemberStatus.ACTIVE))
    if not active_members:
        return Response({"error": "No active members."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        Obligation.objects.bulk_create([
            Obligation(
                organization=org,
                member=member,
                obligation_type=ObligationType.DUES,
                amount_cents=per_member_cents,
                due_date=due_date,
                status=ObligationStatus.OPEN,
                notes=description,
            )
            for member in active_members
        ])

    return Response({
        "ok": True,
        "member_count": len(active_members),
        "per_member_cents": per_member_cents,
        "due_date": str(due_date),
        "description": description,
    })


# ── Family Members ────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def family_members_list(request, member_id):
    from apps.membership.models import FamilyMember
    org = request.organization
    try:
        member = Member.objects.get(id=member_id, organization=org)
    except Member.DoesNotExist:
        return Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        family = FamilyMember.objects.filter(member=member)
        return Response([_serialize_family_member(fm) for fm in family])

    # POST — add a new family member
    required = ["first_name", "last_name", "relationship", "date_of_birth"]
    errors = {f: "Required." for f in required if not request.data.get(f, "").strip()}
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    valid_relationships = {"spouse", "child", "parent", "sibling", "other"}
    if request.data["relationship"] not in valid_relationships:
        return Response({"relationship": "Invalid value."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dob = date.fromisoformat(request.data["date_of_birth"])
    except (ValueError, TypeError):
        return Response({"date_of_birth": "Use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)

    if dob > date.today():
        return Response({"date_of_birth": "Date of birth cannot be in the future."}, status=status.HTTP_400_BAD_REQUEST)

    gender = request.data.get("gender", "").strip()
    if gender and gender not in {"male", "female", "other"}:
        gender = ""

    fm = FamilyMember.objects.create(
        member=member,
        first_name=request.data["first_name"].strip(),
        last_name=request.data["last_name"].strip(),
        first_name_am=request.data.get("first_name_am", "").strip(),
        last_name_am=request.data.get("last_name_am", "").strip(),
        relationship=request.data["relationship"],
        date_of_birth=dob,
        gender=gender,
        notes=request.data.get("notes", "").strip(),
        is_active=True,
    )
    return Response(_serialize_family_member(fm), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes(_ADMIN_PERMISSIONS)
def family_member_detail(request, member_id, fm_id):
    from apps.membership.models import FamilyMember
    org = request.organization
    try:
        member = Member.objects.get(id=member_id, organization=org)
        fm = FamilyMember.objects.get(id=fm_id, member=member)
    except (Member.DoesNotExist, FamilyMember.DoesNotExist):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        fm.is_active = False
        fm.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    updatable = ["first_name", "last_name", "first_name_am", "last_name_am",
                 "relationship", "gender", "notes", "is_active"]
    for field in updatable:
        if field in request.data:
            setattr(fm, field, request.data[field])

    if "date_of_birth" in request.data:
        try:
            dob = date.fromisoformat(request.data["date_of_birth"])
            if dob > date.today():
                return Response({"date_of_birth": "Cannot be in the future."}, status=status.HTTP_400_BAD_REQUEST)
            fm.date_of_birth = dob
        except (ValueError, TypeError):
            return Response({"date_of_birth": "Use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)

    fm.save()
    return Response(_serialize_family_member(fm))


# ── Annual Dues Generation ────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def generate_annual_dues(request):
    """
    Bulk-create fixed annual dues obligations for all active members.
    Skips members who already have a DUES obligation due in the given year.
    """
    org = request.organization
    try:
        year = int(request.data.get("year", 0))
        amount_cents = int(request.data.get("amount_cents", 0))
        due_date_str = request.data.get("due_date", "")
        due_date = date.fromisoformat(due_date_str)
    except (ValueError, TypeError):
        return Response(
            {"error": "Provide valid year (int), amount_cents (int), due_date (YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount_cents <= 0:
        return Response({"error": "amount_cents must be positive."}, status=status.HTTP_400_BAD_REQUEST)
    if year < 2000 or year > 2100:
        return Response({"error": "Invalid year."}, status=status.HTTP_400_BAD_REQUEST)

    description = f"{year} Annual Maintenance Fee"

    active_members = list(Member.objects.filter(organization=org, status=MemberStatus.ACTIVE))

    # Members who already have a dues obligation for this year
    already_billed = set(
        Obligation.objects.filter(
            organization=org,
            obligation_type=ObligationType.DUES,
            due_date__year=year,
        ).values_list("member_id", flat=True)
    )

    to_create = [m for m in active_members if m.id not in already_billed]

    with transaction.atomic():
        Obligation.objects.bulk_create([
            Obligation(
                organization=org,
                member=member,
                obligation_type=ObligationType.DUES,
                amount_cents=amount_cents,
                due_date=due_date,
                status=ObligationStatus.OPEN,
                notes=description,
            )
            for member in to_create
        ])

    return Response({
        "ok": True,
        "created": len(to_create),
        "skipped": len(already_billed),
        "year": year,
        "amount_cents": amount_cents,
        "due_date": str(due_date),
        "description": description,
    })


# ── Bulk Delete Dues ──────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def bulk_delete_dues(request):
    """
    Delete all DUES obligations for a given year (and optional obligation_type filter).
    Only deletes obligations with paid_cents == 0. Partially/fully paid obligations are skipped.
    Body: { year: 2025, confirm: true }
    """
    org = request.organization
    year = request.data.get("year")
    confirm = request.data.get("confirm", False)

    if not year or not confirm:
        return Response(
            {"error": "Provide year and confirm=true."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        year = int(year)
    except (ValueError, TypeError):
        return Response({"error": "year must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    qs = Obligation.objects.filter(
        organization=org,
        obligation_type=ObligationType.DUES,
        due_date__year=year,
    )
    total = qs.count()
    # Only delete obligations with no payments applied
    deletable = qs.filter(paid_cents=0, status__in=[
        ObligationStatus.OPEN, ObligationStatus.CANCELLED,
    ])
    skipped = total - deletable.count()
    deleted_count = deletable.count()

    with transaction.atomic():
        deletable.delete()

    return Response({
        "ok": True,
        "year": year,
        "deleted": deleted_count,
        "skipped_paid": skipped,
        "detail": (
            f"Deleted {deleted_count} obligation(s) for {year}."
            + (f" Skipped {skipped} with payments applied." if skipped else "")
        ),
    })


# ── Reset Dues Deadline ───────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def reset_dues_deadline(request):
    """
    Bulk-reset the due date on open/partially-paid DUES obligations.
    Also clears any accrued penalties so the clock starts fresh from the new date.
    Body: { new_due_date: "2026-07-31", year: 2025 (optional filter) }
    """
    org = request.organization
    new_due_date_str = request.data.get("new_due_date", "")
    year = request.data.get("year")  # optional — if omitted, applies to ALL open dues

    try:
        new_due_date = date.fromisoformat(new_due_date_str)
    except (ValueError, TypeError):
        return Response(
            {"error": "Provide new_due_date in YYYY-MM-DD format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if new_due_date <= date.today():
        return Response(
            {"error": "new_due_date must be a future date."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = Obligation.objects.filter(
        organization=org,
        obligation_type=ObligationType.DUES,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    )
    if year:
        try:
            qs = qs.filter(due_date__year=int(year))
        except (ValueError, TypeError):
            return Response({"error": "year must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    count = qs.count()

    with transaction.atomic():
        qs.update(
            due_date=new_due_date,
            penalty_weeks_applied=0,
            original_amount_cents=None,
        )

    return Response({
        "ok": True,
        "updated": count,
        "new_due_date": str(new_due_date),
        "detail": f"Reset {count} obligation(s) to due date {new_due_date}. Penalty clock restarted.",
    })


# ── Payout Recording ──────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def payouts_list(request):
    """Record or list outgoing payouts (DR PAYOUT_EXP / CR CASH)."""
    org = request.organization

    if request.method == "GET":
        from apps.ledger.models import LedgerTransaction
        qs = LedgerTransaction.objects.filter(
            organization=org,
            source=TransactionSource.PAYOUT,
        ).order_by("-transaction_date")[:50]
        return Response([
            {
                "id": str(t.id),
                "description": t.description,
                "transaction_date": str(t.transaction_date),
                "amount_cents": t.entries.filter(debit_cents__gt=0).aggregate(
                    s=Sum("debit_cents")
                )["s"] or 0,
                "notes": t.notes,
            }
            for t in qs
        ])

    # POST — record a new payout
    try:
        amount_cents = int(request.data.get("amount_cents", 0))
        payout_date = date.fromisoformat(request.data.get("payout_date", ""))
    except (ValueError, TypeError):
        return Response(
            {"error": "Provide valid amount_cents (int) and payout_date (YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount_cents <= 0:
        return Response({"error": "amount_cents must be positive."}, status=status.HTTP_400_BAD_REQUEST)

    description = request.data.get("description", "").strip() or "Event Payout"
    reference = request.data.get("reference", "").strip()
    notes = request.data.get("notes", "").strip()

    try:
        cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
        payout_account = LedgerAccount.objects.get(organization=org, code="PAYOUT_EXP")
    except LedgerAccount.DoesNotExist as exc:
        return Response(
            {"error": f"Ledger account missing: {exc}. Run bootstrap_org first."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    with transaction.atomic():
        txn = LedgerTransaction.objects.create(
            organization=org,
            description=description,
            transaction_date=payout_date,
            source=TransactionSource.PAYOUT,
            posted_by=request.user,
            notes=f"{notes} Ref: {reference}".strip(" Ref:").strip() if reference else notes,
        )
        # DR PAYOUT_EXP (expense increases)
        LedgerEntry.objects.create(
            ledger_transaction=txn,
            account=payout_account,
            debit_cents=amount_cents,
            credit_cents=0,
            description=description,
        )
        # CR CASH (cash decreases)
        LedgerEntry.objects.create(
            ledger_transaction=txn,
            account=cash_account,
            debit_cents=0,
            credit_cents=amount_cents,
            description=f"Payout disbursed — {reference}" if reference else description,
        )

    return Response({
        "ok": True,
        "transaction_id": str(txn.id),
        "amount_cents": amount_cents,
        "payout_date": str(payout_date),
        "description": description,
        "reference": reference,
    }, status=status.HTTP_201_CREATED)


# ── Statement Upload: Parse ────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def statement_parse(request):
    """
    Accept a bank statement PDF or Tithe.ly Excel/CSV upload.
    Returns a preview list of transactions with member matching — no DB writes.
    """
    from .statement_parser import parse_wells_fargo_pdf, parse_tithely_excel, build_preview

    f = request.FILES.get("file")
    if not f:
        return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    filename = f.name.lower()
    file_bytes = f.read()

    try:
        if filename.endswith(".pdf"):
            raw_txns = parse_wells_fargo_pdf(file_bytes)
        elif filename.endswith((".xlsx", ".xls", ".csv")):
            raw_txns = parse_tithely_excel(file_bytes, filename)
        else:
            return Response(
                {"error": "Unsupported file type. Upload a PDF, XLSX, XLS, or CSV."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        return Response({"error": f"Failed to parse file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    org = request.organization
    members = list(Member.objects.filter(organization=org))
    preview = build_preview(raw_txns, members, org)

    matched = sum(1 for p in preview if p["status"] == "matched")
    unmatched = sum(1 for p in preview if p["status"] == "unmatched")
    duplicate = sum(1 for p in preview if p["status"] == "duplicate")

    return Response({
        "filename": f.name,
        "total": len(preview),
        "matched": matched,
        "unmatched": unmatched,
        "duplicate": duplicate,
        "transactions": preview,
    })


# ── Statement Upload: Process ─────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def statement_process(request):
    """
    Process confirmed transactions from a parsed statement.
    Body: { transactions: [...] } — only rows with include=true are recorded.
    Each row must have: matched_member_id (or null), amount_cents, date, method, reference, description.
    """
    from apps.ledger.models import LedgerAccount

    org = request.organization
    rows = request.data.get("transactions", [])
    if not rows:
        return Response({"error": "No transactions provided."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        cash_account = LedgerAccount.objects.get(organization=org, code="CASH")
        contrib_account = LedgerAccount.objects.get(organization=org, code="CONTRIB_REV")
    except LedgerAccount.DoesNotExist as e:
        return Response({"error": f"Ledger account missing: {e}. Run bootstrap_org first."}, status=400)

    posted_by = request.user
    stats = {"recorded": 0, "skipped_duplicate": 0, "skipped_no_member": 0, "errors": []}

    for row in rows:
        if not row.get("include"):
            continue

        try:
            from datetime import date as _date
            pay_date = _date.fromisoformat(row["date"])
            amount_cents = int(row["amount_cents"])
            member_id = row.get("matched_member_id")
            method = row.get("method", "other")
            reference = row.get("reference", "")
            notes = row.get("description", "")
        except (KeyError, ValueError) as e:
            stats["errors"].append(str(e))
            continue

        member = None
        if member_id:
            try:
                member = Member.objects.get(id=member_id, organization=org)
            except Member.DoesNotExist:
                stats["skipped_no_member"] += 1
                continue
        else:
            stats["skipped_no_member"] += 1
            continue

        # Idempotency check
        if Payment.objects.filter(
            organization=org,
            member=member,
            amount_cents=amount_cents,
            payment_date=pay_date,
        ).exists():
            stats["skipped_duplicate"] += 1
            continue

        try:
            with transaction.atomic():
                txn = LedgerTransaction.objects.create(
                    organization=org,
                    description=f"Payment — {member.get_full_name()} {reference}".strip(),
                    transaction_date=pay_date,
                    source=TransactionSource.PAYMENT,
                    posted_by=posted_by,
                    notes=notes,
                )
                LedgerEntry.objects.create(
                    ledger_transaction=txn, account=cash_account,
                    debit_cents=amount_cents, credit_cents=0,
                    member=member, description="Cash/Zelle receipt",
                )
                LedgerEntry.objects.create(
                    ledger_transaction=txn, account=contrib_account,
                    debit_cents=0, credit_cents=amount_cents,
                    member=member, description="Contribution revenue",
                )
                payment = Payment.objects.create(
                    organization=org, member=member,
                    amount_cents=amount_cents, payment_date=pay_date,
                    method=method, reference=reference, notes=notes,
                    ledger_transaction=txn,
                )
                # Auto-apply to oldest open obligations
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

                stats["recorded"] += 1
        except Exception as e:
            stats["errors"].append(f"{member.get_full_name()}: {e}")

    return Response({
        "ok": True,
        "recorded": stats["recorded"],
        "skipped_duplicate": stats["skipped_duplicate"],
        "skipped_no_member": stats["skipped_no_member"],
        "errors": stats["errors"],
    })


# ── Messaging ─────────────────────────────────────────────────────────────────

def _get_recipient_members_qs(org, group, custom_ids=None):
    qs = Member.objects.filter(organization=org)
    if group == "all_active":
        return qs.filter(status=MemberStatus.ACTIVE)
    elif group == "outstanding_dues":
        member_ids = Obligation.objects.filter(
            organization=org,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        ).values_list("member_id", flat=True).distinct()
        return qs.filter(id__in=member_ids, status=MemberStatus.ACTIVE)
    elif group == "suspended":
        return qs.filter(status=MemberStatus.SUSPENDED)
    elif group == "custom":
        return qs.filter(id__in=(custom_ids or []))
    return qs.filter(status=MemberStatus.ACTIVE)


def _serialize_template(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "channel": t.channel,
        "subject": t.subject,
        "body": t.body_en,
        "category": t.category,
        "is_active": t.is_active,
    }


@api_view(["GET", "POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def messaging_templates(request):
    from apps.communications.models import MessageTemplate
    org = request.organization

    if request.method == "GET":
        templates = MessageTemplate.objects.filter(organization=org).order_by("category", "name")
        return Response([_serialize_template(t) for t in templates])

    data = request.data
    name = (data.get("name") or "").strip()
    body = (data.get("body") or "").strip()
    if not name or not body:
        return Response({"detail": "Name and body are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        t = MessageTemplate.objects.create(
            organization=org,
            name=name,
            channel=data.get("channel", "email"),
            subject=(data.get("subject") or "").strip(),
            body_en=body,
            category=(data.get("category") or "").strip(),
        )
        log_action(request, "template_created", f"Created template '{name}'",
                   target_type="template", target_id=str(t.id), target_label=name)
        return Response(_serialize_template(t), status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH", "DELETE"])
@permission_classes(_ADMIN_PERMISSIONS)
def messaging_template_detail(request, template_id):
    from apps.communications.models import MessageTemplate
    org = request.organization
    try:
        t = MessageTemplate.objects.get(id=template_id, organization=org)
    except MessageTemplate.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        name = t.name
        t.delete()
        log_action(request, "template_deleted", f"Deleted template '{name}'",
                   target_type="template", target_id=str(template_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    data = request.data
    if "name" in data:
        t.name = data["name"]
    if "channel" in data:
        t.channel = data["channel"]
    if "subject" in data:
        t.subject = data["subject"]
    if "body" in data:
        t.body_en = data["body"]
    if "category" in data:
        t.category = data["category"]
    if "is_active" in data:
        t.is_active = data["is_active"]
    t.save()
    log_action(request, "template_updated", f"Updated template '{t.name}'",
               target_type="template", target_id=str(t.id), target_label=t.name)
    return Response(_serialize_template(t))


@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def messaging_recipient_count(request):
    org = request.organization
    group = request.query_params.get("group", "all_active")
    channel = request.query_params.get("channel", "email")
    members_qs = _get_recipient_members_qs(org, group)

    if channel == "email":
        count = members_qs.exclude(email="").count()
    elif channel == "sms":
        count = members_qs.filter(
            models.Q(phone__gt="") | models.Q(phone_whatsapp__gt="")
        ).count()
    else:  # both
        email_c = members_qs.exclude(email="").count()
        sms_c = members_qs.filter(
            models.Q(phone__gt="") | models.Q(phone_whatsapp__gt="")
        ).count()
        count = email_c + sms_c

    return Response({"count": count, "member_count": members_qs.count()})


def _render_for_member(text, member):
    """Replace {{variable}} placeholders with member-specific values."""
    open_ob = Obligation.objects.filter(
        member=member,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    ).order_by("due_date").first()

    context = {
        "member_name": f"{member.first_name} {member.last_name}",
        "first_name": member.first_name,
        "last_name": member.last_name,
        "amount_due": f"${open_ob.outstanding_cents / 100:.2f}" if open_ob else "—",
        "due_date": str(open_ob.due_date) if open_ob else "—",
        "event": open_ob.description if open_ob else "—",
        "amount": f"${open_ob.amount_cents / 100:.2f}" if open_ob else "—",
    }
    result = text
    for key, value in context.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


@api_view(["POST"])
@permission_classes(_ADMIN_PERMISSIONS)
def messaging_send(request):
    from apps.communications.tasks import queue_email, queue_sms
    org = request.organization
    data = request.data

    channel = data.get("channel", "email")
    recipient_group = data.get("recipient_group", "all_active")
    custom_member_ids = data.get("member_ids", [])
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()

    if not body:
        return Response({"detail": "Message body is required."}, status=status.HTTP_400_BAD_REQUEST)
    if channel in ("email", "both") and not subject:
        return Response({"detail": "Subject is required for email."}, status=status.HTTP_400_BAD_REQUEST)

    members = list(_get_recipient_members_qs(org, recipient_group, custom_member_ids))
    STOP_FOOTER = "\n\nReply STOP to unsubscribe."
    queued = 0
    skipped = 0

    for member in members:
        rendered_body = _render_for_member(body, member)
        rendered_subject = _render_for_member(subject, member)
        channels = [channel] if channel != "both" else ["email", "sms"]
        for ch in channels:
            if ch == "email":
                if member.email:
                    queue_email(organization=org, member=member,
                                subject=rendered_subject, body=rendered_body)
                    queued += 1
                else:
                    skipped += 1
            elif ch == "sms":
                phone = member.phone_whatsapp or member.phone
                if phone:
                    sms_body = rendered_body if STOP_FOOTER.strip() in rendered_body else rendered_body + STOP_FOOTER
                    queue_sms(organization=org, member=member, body=sms_body)
                    queued += 1
                else:
                    skipped += 1

    group_labels = {
        "all_active": "all active members",
        "outstanding_dues": "members with outstanding dues",
        "suspended": "suspended members",
        "custom": f"{len(members)} selected members",
    }
    log_action(request, "message_sent",
               f"Sent {channel} to {group_labels.get(recipient_group, recipient_group)}: {queued} queued, {skipped} skipped",
               target_type="broadcast")
    detail = f"{queued} messages queued for delivery."
    if skipped:
        detail += f" {skipped} skipped (no valid contact info)."
    return Response({"queued": queued, "skipped": skipped, "detail": detail})


@api_view(["GET"])
@permission_classes(_ADMIN_PERMISSIONS)
def messaging_history(request):
    from apps.communications.models import Communication
    org = request.organization
    qs = (
        Communication.objects.filter(organization=org)
        .select_related("recipient_member")
        .order_by("-created_at")
    )

    channel = request.query_params.get("channel", "").strip()
    if channel:
        qs = qs.filter(channel=channel)

    msg_status = request.query_params.get("status", "").strip()
    if msg_status:
        qs = qs.filter(status=msg_status)

    date_from = request.query_params.get("date_from", "").strip()
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to = request.query_params.get("date_to", "").strip()
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    items, total, page, total_pages = _paginate(qs, request, page_size=25)
    return Response({
        "count": total,
        "page": page,
        "total_pages": total_pages,
        "results": [{
            "id": str(c.id),
            "channel": c.channel,
            "recipient_address": c.recipient_address,
            "recipient_name": (
                f"{c.recipient_member.first_name} {c.recipient_member.last_name}"
                if c.recipient_member else ""
            ),
            "subject": c.subject,
            "body_preview": c.body[:200],
            "status": c.status,
            "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            "created_at": c.created_at.isoformat(),
            "error_message": c.error_message,
        } for c in items],
    })
