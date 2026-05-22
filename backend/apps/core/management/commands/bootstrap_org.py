"""
Management command: bootstrap_org

Creates the default Organization and seeds the chart of accounts.
Run once after the initial migration.

Usage:
    python manage.py bootstrap_org
"""
from django.core.management.base import BaseCommand
from django.conf import settings


CHART_OF_ACCOUNTS = [
    # code, name, account_type
    ("CASH", "Cash & Bank", "asset"),
    ("RECV", "Member Receivables", "asset"),
    ("PAYOUT_PAY", "Payout Payable", "liability"),
    ("EQUITY", "Association Equity", "equity"),
    ("CONTRIB_REV", "Member Contributions Revenue", "revenue"),
    ("PAYOUT_EXP", "Event Payout Expense", "expense"),
    ("WAIVER_EXP", "Obligation Waiver Expense", "expense"),
    ("DUES_REV", "Recurring Dues Revenue", "revenue"),
    ("ADMIN_EXP", "Administrative Expense", "expense"),
]


class Command(BaseCommand):
    help = "Create the default organization and seed the chart of accounts."

    def add_arguments(self, parser):
        parser.add_argument("--name", default=settings.DEFAULT_ORGANIZATION_NAME)
        parser.add_argument("--slug", default="addis-kidan")

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.ledger.models import LedgerAccount

        org, created = Organization.objects.get_or_create(
            slug=options["slug"],
            defaults={"name": options["name"]},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created organization: {org.name}"))
        else:
            self.stdout.write(f"Organization already exists: {org.name}")

        for code, name, account_type in CHART_OF_ACCOUNTS:
            account, acc_created = LedgerAccount.objects.get_or_create(
                organization=org,
                code=code,
                defaults={"name": name, "account_type": account_type},
            )
            status = "Created" if acc_created else "Exists"
            self.stdout.write(f"  [{status}] {code} — {name}")

        self._seed_templates(org)
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

    def _seed_templates(self, org):
        from apps.communications.models import MessageTemplate, CommunicationChannel

        templates = [
            {
                "name": "payment_receipt",
                "channel": CommunicationChannel.EMAIL,
                "subject": "Payment receipt — Addis Kidan",
                "body_en": (
                    "Dear {{member_name}},\n\n"
                    "We have received your payment of {{amount}} on {{date}}.\n"
                    "Payment method: {{method}}\nReference: {{reference}}\n\n"
                    "Thank you for your contribution.\n\n— Addis Kidan Administration"
                ),
            },
            {
                "name": "obligation_reminder",
                "channel": CommunicationChannel.EMAIL,
                "subject": "Contribution reminder — Addis Kidan",
                "body_en": (
                    "Dear {{member_name}},\n\n"
                    "This is a reminder that your contribution of {{amount_due}} for {{event}} "
                    "is due on {{due_date}}.\n\n"
                    "If you have already sent your payment, please disregard this message.\n\n"
                    "Thank you.\n\n— Addis Kidan Administration"
                ),
            },
            {
                "name": "event_announcement",
                "channel": CommunicationChannel.EMAIL,
                "subject": "Association update — Addis Kidan",
                "body_en": (
                    "Dear {{member_name}},\n\n"
                    "We are writing to inform you of a {{event_type}} event affecting "
                    "the {{household_name}} household.\n\n"
                    "Your contribution of {{amount_due}} is due by {{due_date}}.\n\n"
                    "Please keep the family in your thoughts and prayers.\n\n"
                    "— Addis Kidan Administration"
                ),
            },
        ]
        for t in templates:
            obj, created = MessageTemplate.objects.get_or_create(
                organization=org, name=t["name"],
                defaults={k: v for k, v in t.items() if k != "name"},
            )
            status = "Created" if created else "Exists"
            self.stdout.write(f"  [{status}] Template: {t['name']}")
