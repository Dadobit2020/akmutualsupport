"""
Member self-service portal API.

All endpoints here are scoped to request.user.member — the logged-in member
can only ever see their own data.  Admin users can optionally access these
too (their linked member record).
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import FileResponse
from django.db.models import Sum

from apps.obligations.models import Obligation, ObligationStatus, Payment
from apps.membership.models import Member
from apps.ledger.service import get_member_balance_cents


def _get_member(request):
    """Return the Member linked to the current user, or None."""
    user = request.user
    if hasattr(user, "member") and user.member is not None:
        return user.member
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_profile(request):
    """Current member's profile."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    from apps.membership.serializers import MemberSerializer
    return Response(MemberSerializer(member).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def me_update_profile(request):
    """Update own contact information (phone, address, preferred_language only)."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    ALLOWED = {"phone", "phone_whatsapp", "address", "preferred_language"}
    data = {k: v for k, v in request.data.items() if k in ALLOWED}

    from apps.membership.serializers import MemberSerializer
    serializer = MemberSerializer(member, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_balance(request):
    """Current balance summary: outstanding obligations + ledger balance."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    org = request.organization
    open_obligations = Obligation.objects.filter(
        organization=org,
        member=member,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    )
    totals = open_obligations.aggregate(
        total_amount=Sum("amount_cents"),
        total_paid=Sum("paid_cents"),
    )
    total_outstanding = (totals["total_amount"] or 0) - (totals["total_paid"] or 0)
    ledger_balance = get_member_balance_cents(member, org)

    return Response({
        "outstanding_cents": total_outstanding,
        "ledger_balance_cents": ledger_balance,
        "open_obligation_count": open_obligations.count(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_obligations(request):
    """All obligations for the current member, newest first."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    org = request.organization
    qs = Obligation.objects.filter(
        organization=org, member=member
    ).select_related("event").order_by("-due_date")

    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status__in=status_filter.split(","))

    from apps.obligations.serializers import ObligationSerializer
    return Response(ObligationSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_payments(request):
    """All payments recorded for the current member."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    org = request.organization
    payments = Payment.objects.filter(
        organization=org, member=member
    ).prefetch_related("applications").order_by("-payment_date")

    from apps.obligations.serializers import PaymentSerializer
    return Response(PaymentSerializer(payments, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_receipt(request, payment_id):
    """Download a PDF receipt for a specific payment."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    org = request.organization
    try:
        payment = Payment.objects.get(id=payment_id, member=member, organization=org)
    except Payment.DoesNotExist:
        return Response({"detail": "Payment not found."}, status=404)

    from apps.portal.pdf import generate_receipt_pdf
    pdf_buffer = generate_receipt_pdf(payment, org)
    return FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=f"receipt-{str(payment.id)[:8]}.pdf",
        content_type="application/pdf",
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_statement(request):
    """Download a PDF statement of the member's full obligation history."""
    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    org = request.organization
    from apps.portal.pdf import generate_member_statement_pdf
    pdf_buffer = generate_member_statement_pdf(member, org)
    return FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=f"statement-{member.last_name.lower()}.pdf",
        content_type="application/pdf",
    )
