import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="obligations.Payment")
def send_payment_receipt(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.member or not instance.member.email:
        return

    try:
        _do_send_receipt(instance)
    except Exception:
        logger.exception(f"Failed to queue receipt email for payment {instance.id} — payment itself is recorded.")


def _do_send_receipt(instance):
    from apps.communications.tasks import queue_email
    from apps.communications.models import MessageTemplate

    org = instance.organization
    member = instance.member

    try:
        template = MessageTemplate.objects.get(organization=org, name="payment_receipt")
    except MessageTemplate.DoesNotExist:
        template = None

    context = {
        "member_name": member.get_full_name(),
        "amount": f"${instance.amount_cents / 100:.2f}",
        "date": instance.payment_date.strftime("%B %d, %Y"),
        "method": instance.get_method_display() if hasattr(instance, "get_method_display") else instance.method,
        "reference": instance.reference or "N/A",
    }

    if template:
        subject, body = template.render(context, language=member.preferred_language)
    else:
        subject = f"Payment receipt — Addis Kidan"
        body = (
            f"Dear {context['member_name']},\n\n"
            f"We have received your payment of {context['amount']} on {context['date']}.\n"
            f"Payment method: {context['method']}\n"
            f"Reference: {context['reference']}\n\n"
            f"Thank you for your contribution to the Addis Kidan Mutual Support Association.\n\n"
            f"— Addis Kidan Administration"
        )

    queue_email(
        organization=org,
        member=member,
        subject=subject,
        body=body,
        template=template,
        payment=instance,
    )



