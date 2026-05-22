"""
PDF generation for member receipts and statements.
Uses reportlab — simple, dependency-free, no external services needed.
"""
import io
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

GREEN = colors.HexColor("#1a5c2e")
LIGHT_GREEN = colors.HexColor("#f0f7f3")
GRAY = colors.HexColor("#6b7280")
DARK = colors.HexColor("#111827")


def _base_doc(buffer, title: str):
    return SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
    )


def _header_elements(org_name: str, doc_title: str, styles) -> list:
    title_style = ParagraphStyle("OrgTitle", fontSize=16, textColor=GREEN, fontName="Helvetica-Bold", spaceAfter=2)
    sub_style = ParagraphStyle("DocSub", fontSize=10, textColor=GRAY, fontName="Helvetica", spaceAfter=4)
    date_style = ParagraphStyle("Date", fontSize=9, textColor=GRAY, fontName="Helvetica", alignment=TA_RIGHT)

    return [
        Paragraph(org_name, title_style),
        Paragraph(doc_title, sub_style),
        HRFlowable(width="100%", thickness=1, color=GREEN),
        Spacer(1, 0.15 * inch),
    ]


def generate_receipt_pdf(payment, org) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = _base_doc(buffer, "Payment Receipt")
    styles = getSampleStyleSheet()
    story = []

    story += _header_elements(org.name, "Payment Receipt", styles)

    # Receipt details table
    member = payment.member
    receipt_data = [
        ["Receipt date:", datetime.date.today().strftime("%B %d, %Y")],
        ["Member:", member.get_full_name() if member else "—"],
        ["Payment date:", payment.payment_date.strftime("%B %d, %Y")],
        ["Method:", payment.method.replace("_", " ").title()],
        ["Reference:", payment.reference or "—"],
    ]

    label_style = ParagraphStyle("Label", fontSize=10, textColor=GRAY, fontName="Helvetica")
    value_style = ParagraphStyle("Value", fontSize=10, textColor=DARK, fontName="Helvetica-Bold")

    for label, value in receipt_data:
        story.append(Table(
            [[Paragraph(label, label_style), Paragraph(value, value_style)]],
            colWidths=[2 * inch, 4.5 * inch],
            style=TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 4)]),
        ))

    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.1 * inch))

    # Amount
    amount_style = ParagraphStyle("Amount", fontSize=22, textColor=GREEN, fontName="Helvetica-Bold", alignment=TA_CENTER)
    story.append(Paragraph(f"${payment.amount_cents / 100:,.2f}", amount_style))
    story.append(Paragraph("Amount Received", ParagraphStyle("AmtLabel", fontSize=10, textColor=GRAY, alignment=TA_CENTER)))

    # Applications
    applications = list(payment.applications.select_related("obligation__event").all())
    if applications:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph("Applied to:", ParagraphStyle("AppHdr", fontSize=10, fontName="Helvetica-Bold", textColor=DARK)))
        story.append(Spacer(1, 0.08 * inch))
        app_data = [["Obligation", "Applied"]]
        for app in applications:
            desc = str(app.obligation.event) if app.obligation.event else "Recurring dues"
            app_data.append([desc, f"${app.applied_cents / 100:,.2f}"])
        t = Table(app_data, colWidths=[4.5 * inch, 2 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREEN),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

    story.append(Spacer(1, 0.4 * inch))
    footer = ParagraphStyle("Footer", fontSize=8, textColor=GRAY, alignment=TA_CENTER)
    story.append(Paragraph(f"Thank you for your contribution to {org.name}.", footer))
    story.append(Paragraph(f"Receipt ID: {str(payment.id)}", footer))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_member_statement_pdf(member, org) -> io.BytesIO:
    from apps.obligations.models import Obligation, ObligationStatus, Payment

    buffer = io.BytesIO()
    doc = _base_doc(buffer, "Member Statement")
    styles = getSampleStyleSheet()
    story = []

    story += _header_elements(org.name, "Member Statement", styles)

    # Member info
    info_style = ParagraphStyle("Info", fontSize=10, textColor=DARK, fontName="Helvetica", spaceAfter=3)
    story.append(Paragraph(f"<b>Member:</b> {member.get_full_name()}", info_style))
    story.append(Paragraph(f"<b>Email:</b> {member.email or '—'}", info_style))
    story.append(Paragraph(f"<b>Statement date:</b> {datetime.date.today().strftime('%B %d, %Y')}", info_style))
    story.append(Spacer(1, 0.2 * inch))

    # Balance summary
    obligations = Obligation.objects.filter(organization=org, member=member)
    total_owed = sum(o.amount_cents for o in obligations if o.status not in ("waived", "cancelled", "written_off"))
    total_paid = sum(o.paid_cents for o in obligations)
    outstanding = sum(o.outstanding_cents for o in obligations if o.status in (ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID))

    summary_data = [
        ["Total obligations", f"${total_owed / 100:,.2f}"],
        ["Total paid", f"${total_paid / 100:,.2f}"],
        ["Outstanding balance", f"${outstanding / 100:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 3.5 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.25 * inch))

    # Obligations table
    story.append(Paragraph("Contribution History", ParagraphStyle("SecHdr", fontSize=11, fontName="Helvetica-Bold", textColor=GREEN, spaceAfter=6)))

    obl_data = [["Event / Type", "Amount", "Paid", "Due Date", "Status"]]
    for o in obligations.select_related("event").order_by("-due_date"):
        event_desc = str(o.event) if o.event else "Recurring dues"
        if len(event_desc) > 40:
            event_desc = event_desc[:37] + "..."
        obl_data.append([
            event_desc,
            f"${o.amount_cents / 100:,.2f}",
            f"${o.paid_cents / 100:,.2f}",
            o.due_date.strftime("%m/%d/%Y"),
            o.status.replace("_", " ").title(),
        ])

    if len(obl_data) > 1:
        t = Table(obl_data, colWidths=[2.5 * inch, 0.9 * inch, 0.9 * inch, 1 * inch, 1.2 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No obligations found.", info_style))

    # Payment history
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Payment History", ParagraphStyle("SecHdr2", fontSize=11, fontName="Helvetica-Bold", textColor=GREEN, spaceAfter=6)))

    payments = Payment.objects.filter(organization=org, member=member).order_by("-payment_date")
    pay_data = [["Date", "Amount", "Method", "Reference"]]
    for p in payments:
        pay_data.append([
            p.payment_date.strftime("%m/%d/%Y"),
            f"${p.amount_cents / 100:,.2f}",
            p.method.replace("_", " ").title(),
            p.reference or "—",
        ])

    if len(pay_data) > 1:
        t = Table(pay_data, colWidths=[1 * inch, 1 * inch, 1.5 * inch, 3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No payments recorded.", info_style))

    story.append(Spacer(1, 0.4 * inch))
    footer = ParagraphStyle("Footer", fontSize=8, textColor=GRAY, alignment=TA_CENTER)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(f"{org.name} · Generated {datetime.date.today().strftime('%B %d, %Y')}", footer))

    doc.build(story)
    buffer.seek(0)
    return buffer
