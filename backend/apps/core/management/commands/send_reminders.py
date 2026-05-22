"""
Management command: send_reminders

Dispatches obligation reminder emails for all active organizations.
Called daily by the Render cron job (see render.yaml).
Can also be run manually: python manage.py send_reminders

This command enqueues Celery tasks (which in turn send the emails),
so it returns quickly even for large member counts.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Queue obligation reminder emails for all active organizations."

    def handle(self, *args, **options):
        from apps.identity.models import Organization
        from apps.obligations.tasks import send_obligation_reminders

        orgs = Organization.objects.filter(is_active=True)
        count = 0
        for org in orgs:
            send_obligation_reminders.delay(str(org.id))
            count += 1
            self.stdout.write(f"  Queued reminders for: {org.name}")

        self.stdout.write(self.style.SUCCESS(f"Queued reminder tasks for {count} organization(s)."))
