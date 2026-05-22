"""
Email dispatch tasks. All sends go through the queue — never synchronously in a web request.
"""
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


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
            send_mail(
                subject=comm.subject,
                message=comm.body,
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[comm.recipient_address],
                fail_silently=False,
            )
        comm.status = CommunicationStatus.SENT
        comm.sent_at = timezone.now()
        comm.save(update_fields=["status", "sent_at", "updated_at"])
    except Exception as exc:
        logger.exception(f"Failed to send communication {communication_id}: {exc}")
        comm.status = CommunicationStatus.FAILED
        comm.error_message = str(exc)
        comm.save(update_fields=["status", "error_message", "updated_at"])
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


def queue_email(
    *,
    organization,
    member,
    subject: str,
    body: str,
    template=None,
    obligation=None,
    payment=None,
) -> "Communication":
    from .models import Communication, CommunicationChannel, CommunicationStatus

    address = member.email
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
