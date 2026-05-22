"""
Management command: setup_periodic_tasks

Seeds the Celery Beat periodic task schedule in the database.
Run once after `bootstrap_org`. Safe to re-run (uses get_or_create).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create Celery Beat periodic tasks for all active organizations."

    def handle(self, *args, **options):
        from django_celery_beat.models import PeriodicTask, CrontabSchedule
        from apps.identity.models import Organization
        import json

        # Daily reminder schedule: 9am UTC
        daily_9am, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="9", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        # Monthly dues: 1st of each month at 6am UTC
        monthly_1st, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="6", day_of_week="*", day_of_month="1", month_of_year="*"
        )

        orgs = Organization.objects.filter(is_active=True)
        for org in orgs:
            PeriodicTask.objects.get_or_create(
                name=f"send_reminders_{org.slug}",
                defaults={
                    "crontab": daily_9am,
                    "task": "apps.obligations.tasks.send_obligation_reminders",
                    "args": json.dumps([str(org.id)]),
                    "enabled": True,
                },
            )
            PeriodicTask.objects.get_or_create(
                name=f"generate_dues_{org.slug}",
                defaults={
                    "crontab": monthly_1st,
                    "task": "apps.obligations.tasks.generate_recurring_dues",
                    "args": json.dumps([str(org.id)]),
                    "enabled": True,
                },
            )
            self.stdout.write(f"  Scheduled tasks for: {org.name}")

        self.stdout.write(self.style.SUCCESS("Periodic tasks configured."))
