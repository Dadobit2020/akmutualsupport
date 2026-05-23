"""
Notification dispatch tasks — email via SendGrid SMTP, SMS via Twilio.
All sends are async (Celery); never call these directly from a web request.
"""
import logging
from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Core dispatch task ────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_communication(self, communication_id: str):
    from .models import Communication, CommunicationStatus, CommunicationChannel

    try:
        comm = Communication.objects.get(id=communication_id)
    except Communication.DoesNotExist:
        logger.error(f"Communication {communication_id} not found")
        return

    if comm.status not in (CommunicationStatus.QUEUED,):
        return

    try:
        if comm.channel == CommunicationChannel.EMAIL:
            _send_email(comm)
        elif comm.channel == CommunicationChannel.SMS:
            _send_sms(comm)

        comm.status = CommunicationStatus.SENT
        comm.sent_at = timezone.now()
        comm.save(update_fields=["status", "sent_at", "updated_at"])

    except Exception as exc:
        logger.exception(f"Failed to send communication {communication_id}: {exc}")
        comm.status = CommunicationStatus.FAILED
        comm.error_message = str(exc)
        comm.save(update_fields=["status", "error_message", "updated_at"])
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# ── Email ─────────────────────────────────────────────────────────────────────

def _send_email(comm):
    """Send via Django email backend (SendGrid SMTP in production)."""
    from django.conf import settings

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@addiskidan.org")

    # Use HTML-capable message so body renders nicely
    msg = EmailMultiAlternatives(
        subject=comm.subject,
        body=comm.body,
        from_email=from_email,
        to=[comm.recipient_address],
    )
    # If body looks like it contains HTML, attach as html alternative
    if "<" in comm.body and ">" in comm.body:
        msg.attach_alternative(comm.body, "text/html")

    msg.send(fail_silently=False)
    logger.info(f"Email sent to {comm.recipient_address}: {comm.subject}")


# ── SMS ───────────────────────────────────────────────────────────────────────

def _send_sms(comm):
    """Send via Twilio REST API."""
    from django.conf import settings

    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        raise RuntimeError("Twilio credentials not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER).")

    from twilio.rest import Client
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body=comm.body,
        from_=from_number,
        to=comm.recipient_address,
    )
    comm.provider_message_id = message.sid
    comm.save(update_fields=["provider_message_id", "updated_at"])
    logger.info(f"SMS sent to {comm.recipient_address} (sid={message.sid})")


# ── Helpers — queue a message and fire the async task ────────────────────────

def queue_email(
    *,
    organization,
    member=None,
    recipient_address: str = "",
    subject: str,
    body: str,
    template=None,
    obligation=None,
    payment=None,
) -> "Communication | None":
    from .models import Communication, CommunicationChannel, CommunicationStatus

    address = recipient_address or (member.email if member else "")
    if not address:
        return None

    comm = Communication.objects.create(
        organization=organization,
        recipient_member=member,
        channel=CommunicationChannel.EMAIL,
        recipient_address=address,
        subject=subject,
        body=body,
        template=template,
        status=CommunicationStatus.QUEUED,
        obligation=obligation,
        payment=payment,
    )
    send_communication.delay(str(comm.id))
    return comm


def queue_sms(
    *,
    organization,
    member=None,
    recipient_phone: str = "",
    body: str,
    template=None,
    obligation=None,
    payment=None,
) -> "Communication | None":
    from .models import Communication, CommunicationChannel, CommunicationStatus
    from django.conf import settings

    # Skip silently if Twilio not configured
    if not getattr(settings, "TWILIO_ACCOUNT_SID", ""):
        logger.debug("SMS skipped — TWILIO_ACCOUNT_SID not set.")
        return None

    phone = recipient_phone or (member.phone_whatsapp or member.phone if member else "")
    if not phone:
        return None

    # Truncate to 1600 chars (Twilio's max for a single API call)
    body = body[:1600]

    comm = Communication.objects.create(
        organization=organization,
        recipient_member=member,
        channel=CommunicationChannel.SMS,
        recipient_address=phone,
        subject="",
        body=body,
        template=template,
        status=CommunicationStatus.QUEUED,
        obligation=obligation,
        payment=payment,
    )
    send_communication.delay(str(comm.id))
    return comm
