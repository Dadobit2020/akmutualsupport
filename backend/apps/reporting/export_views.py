"""
Treasurer export center — CSV and PDF downloads for admin users.
All exports are scoped to request.organization and require IsAdminRole.
"""
import csv
import datetime
import io

from django.http import HttpResponse, FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.identity.permissions import IsAdminRole
from apps.membership.models import Member, MemberStatus
from apps.obligations.models import Obligation, ObligationStatus, Payment
from apps.ledger.models import LedgerEntry


# ── Members ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_members_csv(request):
    org = request.organization
    members = Member.objects.filter(organization=org).select_related(
        "household", "contribution_rule"
    ).order_by("last_name", "first_name")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="members_{datetime.date.today()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "ID", "First Name", "Last Name", "Email", "Phone",
        "Status", "Tier", "Household", "Join Date", "Payment Reference",
    ])
    for m in members:
        writer.writerow([
            str(m.id), m.first_name, m.last_name, m.email, m.phone,
            m.status, m.tier,
            m.household.name if m.household else "",
            m.join_date.isoformat(),
            m.payment_reference or "",
        ])

    return response


# ── Obligations ───────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_obligations_csv(request):
    org = request.organization
    status_filter = request.query_params.get("status")

    qs = Obligation.objects.filter(organization=org).select_related(
        "member", "event"
    ).order_by("-due_date", "member__last_name")

    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",")]
        qs = qs.filter(status__in=statuses)

    response = HttpResponse(content_type="text/csv")
    filename = f"obligations_{datetime.date.today()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Obligation ID", "Member", "Email", "Event / Type",
        "Amount ($)", "Paid ($)", "Outstanding ($)",
        "Due Date", "Status", "Waiver Reason",
    ])
    for o in qs:
        writer.writerow([
            str(o.id),
            o.member.get_full_name(),
            o.member.email,
            str(o.event) if o.event else "Recurring dues",
            f"{o.amount_cents / 100:.2f}",
            f"{o.paid_cents / 100:.2f}",
            f"{o.outstanding_cents / 100:.2f}",
            o.due_date.isoformat(),
            o.status,
            o.waiver_reason,
        ])

    return response


# ── Payments ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_payments_csv(request):
    org = request.organization

    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")

    qs = Payment.objects.filter(organization=org).select_related(
        "member", "ledger_transaction__posted_by"
    ).order_by("-payment_date")

    if date_from:
        try:
            qs = qs.filter(payment_date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(payment_date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass

    response = HttpResponse(content_type="text/csv")
    filename = f"payments_{datetime.date.today()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Payment ID", "Member", "Email",
        "Amount ($)", "Method", "Reference", "Payment Date", "Recorded By",
    ])
    for p in qs:
        writer.writerow([
            str(p.id),
            p.member.get_full_name() if p.member else "—",
            p.member.email if p.member else "—",
            f"{p.amount_cents / 100:.2f}",
            p.method.replace("_", " ").title(),
            p.reference or "",
            p.payment_date.isoformat(),
            str(p.ledger_transaction.posted_by) if p.ledger_transaction and p.ledger_transaction.posted_by else "",
        ])

    return response


# ── Ledger entries ────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_ledger_csv(request):
    org = request.organization

    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")

    qs = LedgerEntry.objects.filter(
        ledger_transaction__organization=org
    ).select_related(
        "ledger_transaction", "account"
    ).order_by("-ledger_transaction__transaction_date", "-ledger_transaction__created_at")

    if date_from:
        try:
            qs = qs.filter(ledger_transaction__transaction_date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(ledger_transaction__transaction_date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass

    response = HttpResponse(content_type="text/csv")
    filename = f"ledger_{datetime.date.today()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Transaction ID", "Date", "Description",
        "Account Code", "Account Name", "Debit ($)", "Credit ($)",
        "Source", "Posted By",
    ])
    for e in qs:
        txn = e.ledger_transaction
        writer.writerow([
            str(txn.id),
            txn.transaction_date.isoformat(),
            txn.description,
            e.account.code,
            e.account.name,
            f"{e.debit_cents / 100:.2f}" if e.debit_cents else "",
            f"{e.credit_cents / 100:.2f}" if e.credit_cents else "",
            txn.source,
            str(txn.posted_by) if txn.posted_by else "",
        ])

    return response


# ── Member statement PDF (admin pull) ────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_member_statement_pdf(request, member_id):
    org = request.organization
    try:
        member = Member.objects.get(id=member_id, organization=org)
    except Member.DoesNotExist:
        from rest_framework.response import Response
        return Response({"detail": "Member not found."}, status=404)

    from apps.portal.pdf import generate_member_statement_pdf
    buffer = generate_member_statement_pdf(member, org)
    filename = f"statement_{member.last_name}_{member.first_name}_{datetime.date.today()}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type="application/pdf")


# ── Outstanding balances CSV ──────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_outstanding_csv(request):
    org = request.organization

    from django.db.models import Sum
    data = (
        Obligation.objects.filter(
            organization=org,
            status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
        )
        .values(
            "member__id", "member__first_name", "member__last_name",
            "member__email", "member__phone",
        )
        .annotate(total_owed=Sum("amount_cents"), total_paid=Sum("paid_cents"))
        .order_by("-total_owed")
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"outstanding_balances_{datetime.date.today()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Member ID", "Name", "Email", "Phone",
        "Total Owed ($)", "Total Paid ($)", "Outstanding ($)",
    ])
    for row in data:
        owed = row["total_owed"] or 0
        paid = row["total_paid"] or 0
        writer.writerow([
            str(row["member__id"]),
            f"{row['member__first_name']} {row['member__last_name']}",
            row["member__email"],
            row["member__phone"],
            f"{owed / 100:.2f}",
            f"{paid / 100:.2f}",
            f"{(owed - paid) / 100:.2f}",
        ])

    return response
