"""
User lifecycle signals — invite email on new account creation.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings

logger = logging.getLogger(__name__)


@receiver(post_save, sender="identity.User")
def send_invite_email(sender, instance, created, **kwargs):
    """Send a welcome / password-setup email when a new non-superuser account is created."""
    if not created:
        return
    if instance.is_superuser:
        return
    # Only send if the account has no usable password set (invite flow)
    if instance.has_usable_password():
        return

    _queue_invite(instance)


def _queue_invite(user):
    """Build and queue the invite email. Safe to call after transaction commits."""
    try:
        from apps.identity.models import UserOrganizationRole
        from apps.communications.tasks import queue_email

        role_qs = UserOrganizationRole.objects.filter(user=user, is_active=True).select_related("organization")
        org = role_qs.first().organization if role_qs.exists() else None
        if org is None:
            logger.warning(f"Invite for {user.email}: no active org role found, skipping email.")
            return

        token_generator = PasswordResetTokenGenerator()
        uid = urlsafe_base64_encode(force_bytes(str(user.id)))
        token = token_generator.make_token(user)

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?uid={uid}&token={token}"

        member = getattr(user, "member", None)
        member_for_email = member if member else None

        subject = f"Welcome to {org.name} — Set up your account"
        body = (
            f"Hi {user.first_name},\n\n"
            f"Your account for {org.name} has been created.\n\n"
            f"Click the link below to set your password and log in:\n"
            f"{setup_link}\n\n"
            f"This link expires after 3 days.\n\n"
            f"If you did not expect this email, please contact your administrator.\n\n"
            f"{org.name}"
        )

        if not user.email:
            return

        if member_for_email:
            queue_email(
                organization=org,
                member=member_for_email,
                subject=subject,
                body=body,
            )
        else:
            from apps.communications.models import Communication, CommunicationChannel, CommunicationStatus
            from apps.communications.tasks import send_communication
            comm = Communication.objects.create(
                organization=org,
                channel=CommunicationChannel.EMAIL,
                recipient_address=user.email,
                subject=subject,
                body=body,
                status=CommunicationStatus.QUEUED,
            )
            send_communication.delay(str(comm.id))

    except Exception:
        logger.exception(f"Failed to queue invite email for {user.email}")
