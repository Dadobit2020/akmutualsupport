"""
User lifecycle signals — welcome email + SMS on new account creation.
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
def send_welcome_notifications(sender, instance, created, **kwargs):
    """
    On new non-superuser account creation (invite flow — no password set yet):
      • Email: "Your account is ready — set your password" with a secure link
      • SMS:   Short alert directing them to check email / portal (if phone on file)
    """
    if not created:
        return
    if instance.is_superuser:
        return
    if instance.has_usable_password():
        return

    # Run after the transaction commits so all FKs are readable
    from django.db import transaction
    transaction.on_commit(lambda: _send_welcome(instance))


def _send_welcome(user):
    try:
        from apps.identity.models import UserOrganizationRole
        from apps.communications.tasks import queue_email, queue_sms

        role_qs = UserOrganizationRole.objects.filter(user=user, is_active=True).select_related("organization")
        org = role_qs.first().organization if role_qs.exists() else None
        if org is None:
            logger.warning(f"Welcome notification for {user.email}: no org role, skipping.")
            return

        # Build password-setup link
        uid = urlsafe_base64_encode(force_bytes(str(user.id)))
        token = PasswordResetTokenGenerator().make_token(user)
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?uid={uid}&token={token}"

        member = getattr(user, "member", None)
        name = user.first_name or "Member"

        # ── Welcome email ─────────────────────────────────────────────────────
        if user.email:
            subject = f"Welcome to {org.name} — Set up your account"
            body = (
                f"Hi {name},\n\n"
                f"Your account for {org.name} has been created.\n\n"
                f"Click the link below to set your password and access the member portal:\n\n"
                f"  {setup_link}\n\n"
                f"This link expires in 3 days. Once you set your password you can:\n"
                f"  • View your outstanding contributions and due dates\n"
                f"  • Download your account statement\n"
                f"  • Make payments online via our secure payment portal\n"
                f"  • Chat with our AI assistant for instant answers\n\n"
                f"If you did not expect this email, please contact the association office.\n\n"
                f"— {org.name}"
            )
            queue_email(
                organization=org,
                member=member,
                recipient_address=user.email,
                subject=subject,
                body=body,
            )
            logger.info(f"Welcome email queued for {user.email}")

        # ── Welcome SMS ───────────────────────────────────────────────────────
        # SMS is a brief alert; the full setup link is in the email.
        phone = (member.phone_whatsapp or member.phone) if member else ""
        if phone:
            sms_body = (
                f"Hi {name}, welcome to {org.name}! "
                f"Your member portal account is ready. "
                f"Check your email to set your password and log in. "
                f"Questions? Visit {frontend_url}"
            )
            queue_sms(
                organization=org,
                member=member,
                recipient_phone=phone,
                body=sms_body,
            )
            logger.info(f"Welcome SMS queued for {phone}")

    except Exception:
        logger.exception(f"Failed to send welcome notifications for {user.email}")
