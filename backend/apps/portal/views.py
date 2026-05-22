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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def me_chat(request):
    """
    AI assistant endpoint. Accepts a message + optional conversation history,
    returns a GPT-4o-mini response with the member's account data in context.

    Request body:
        { "message": "...", "history": [{"role": "user"|"assistant", "content": "..."}] }
    """
    from django.conf import settings
    import openai as openai_lib

    member = _get_member(request)
    if not member:
        return Response({"detail": "No member account linked to this user."}, status=404)

    message = (request.data.get("message") or "").strip()
    if not message:
        return Response({"detail": "message is required."}, status=400)

    # Limit history to last 10 turns to keep token usage down
    history = request.data.get("history", [])
    if not isinstance(history, list):
        history = []
    history = history[-10:]

    org = request.organization

    # ── Build member context for the system prompt ─────────────────────────────
    open_obligations = Obligation.objects.filter(
        organization=org,
        member=member,
        status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
    ).select_related("event").order_by("due_date")

    paid_obligations = Obligation.objects.filter(
        organization=org, member=member, status=ObligationStatus.PAID
    ).count()

    recent_payments = Payment.objects.filter(
        organization=org, member=member
    ).order_by("-payment_date")[:5]

    from django.db.models import Sum
    totals = open_obligations.aggregate(
        total_amount=Sum("amount_cents"), total_paid=Sum("paid_cents")
    )
    total_outstanding = (totals["total_amount"] or 0) - (totals["total_paid"] or 0)

    obligations_text = ""
    if open_obligations.exists():
        lines = []
        for o in open_obligations:
            desc = o.event.description if o.event else o.notes or "Recurring dues"
            outstanding = o.amount_cents - o.paid_cents
            lines.append(
                f"  • {desc}: ${outstanding/100:.2f} outstanding"
                f" (due {o.due_date.strftime('%B %d, %Y')}, status: {o.status})"
            )
        obligations_text = "\n".join(lines)
    else:
        obligations_text = "  • No open obligations — all caught up!"

    payments_text = ""
    if recent_payments:
        lines = []
        for p in recent_payments:
            lines.append(
                f"  • ${p.amount_cents/100:.2f} on {p.payment_date.strftime('%B %d, %Y')}"
                f" via {p.method.replace('_', ' ')}"
                + (f" (ref: {p.reference})" if p.reference else "")
            )
        payments_text = "\n".join(lines)
    else:
        payments_text = "  • No payments recorded yet."

    member_context = (
        f"Name: {member.get_full_name()}\n"
        f"Member since: {member.join_date.strftime('%B %d, %Y')}\n"
        f"Status: {member.status}\n"
        f"Email: {member.email or '(not on file)'}\n"
        f"Phone: {member.phone or '(not on file)'}\n\n"
        f"OPEN OBLIGATIONS (total outstanding: ${total_outstanding/100:.2f}):\n{obligations_text}\n\n"
        f"RECENT PAYMENTS:\n{payments_text}\n\n"
        f"Paid obligations (historical count): {paid_obligations}"
    )

    system_prompt = f"""You are the virtual assistant for Addis Kidan Mutual Support Association (AKMSA), \
an Ethiopian-American mutual aid organization based in the United States. \
Your role is to help members understand their account, benefits, obligations, and association policies.

━━ ABOUT AKMSA ━━
Addis Kidan Mutual Support Association brings together members who support each other \
through life's most difficult moments — especially bereavement. Members pay into a shared \
fund and receive support when a death occurs in their family.

━━ KEY POLICIES (BYLAWS SUMMARY) ━━
• Registration fee: $200 per member (one-time, paid on joining)
• Death benefit — member or spouse/parent: $15,000 payout to the bereaved household (Article 13.1)
• Death benefit — dependent (child, sibling): $3,000 payout (Article 13.2)
• Special contribution: When a death event occurs, the $15,000 is collected equally from \
  all active members (e.g., $15,000 ÷ 300 members = $50 each) (Article 12.1)
• Contribution window: Members have 15 days to pay after an event is announced (Article 13.7)
• Annual maintenance fee: $50/year per member until the association reaches a $100,000 reserve (Article 12.2)
• Payments accepted via Tithe.ly (online), check, cash, or bank transfer
• Members who do not pay within the window may be suspended (Article 14)

━━ CURRENT MEMBER ACCOUNT ━━
{member_context}

━━ INSTRUCTIONS ━━
- Be warm, respectful, and helpful — many members speak Amharic; respond in whatever \
  language the member uses (English or Amharic)
- Use the member account data above to answer account-specific questions
- To get a full PDF statement, direct the member to: Contributions page → download statement
- You CANNOT process payments or change account data — for payments, direct them to \
  the "Pay Online" button (Tithe.ly) on the dashboard or contributions page
- For issues that need admin action, say "please contact the association office"
- Keep answers concise and clear; use bullet points for lists
- If asked about an obligation, explain what it is (event vs. annual dues) and when it's due
- Today's date is {__import__('datetime').date.today().strftime('%B %d, %Y')}
"""

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return Response(
            {"detail": "AI assistant is not configured. Please contact the administrator."},
            status=503,
        )

    try:
        client = openai_lib.OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message},
            ],
        )
        return Response({"response": completion.choices[0].message.content})
    except openai_lib.APIError as e:
        return Response({"detail": f"AI service error: {str(e)}"}, status=502)
    except Exception:
        return Response({"detail": "Unexpected error from AI service."}, status=500)


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
