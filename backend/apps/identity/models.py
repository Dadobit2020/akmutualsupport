import uuid
import pyotp
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.core.models import TimeStampedModel


class Organization(TimeStampedModel):
    """
    A mutual-support association. Single row in v1; `organization_id` discipline on all tables
    keeps Phase 3 multi-tenancy possible without schema rewrites.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    is_active = models.BooleanField(default=True)
    # Configurable policy fields
    default_payout_amount_cents = models.PositiveIntegerField(
        default=0,
        help_text="Default payout for a bereavement event, in cents.",
    )
    contribution_deadline_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="Days after event approval before member contributions are due.",
    )
    currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=64, default="America/New_York")
    # Contact / branding
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "organization"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # MFA
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True)

    # Linked to a Member record (optional — admins may not be members)
    member = models.OneToOneField(
        "membership.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def generate_mfa_secret(self):
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret

    def verify_mfa_token(self, token: str) -> bool:
        if not self.mfa_secret:
            return False
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(token)

    class Meta:
        db_table = "auth_user"


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    TREASURER = "treasurer", "Treasurer"
    SECRETARY = "secretary", "Secretary"
    CHAIRPERSON = "chairperson", "Chairperson"
    MEMBER = "member", "Member"


# Roles that require MFA
MFA_REQUIRED_ROLES = {Role.SUPER_ADMIN, Role.TREASURER}


class UserOrganizationRole(TimeStampedModel):
    """Maps a user to a role within an organization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="org_roles")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=20, choices=Role.choices)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="granted_roles",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_organization_role"
        unique_together = [("user", "organization", "role")]

    def __str__(self):
        return f"{self.user.email} — {self.role} @ {self.organization}"
