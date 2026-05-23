import uuid
from django.db import models
from apps.core.models import TimeStampedModel, OrganizationScopedModel


class MemberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    INACTIVE = "inactive", "Inactive"
    DECEASED = "deceased", "Deceased"
    LEFT = "left", "Left"


class MembershipTier(models.TextChoices):
    STANDARD = "standard", "Standard"
    SENIOR = "senior", "Senior"
    FAMILY = "family", "Family"


class ContributionType(models.TextChoices):
    FULL = "full", "Full"
    PARTIAL = "partial", "Partial"
    EXEMPT = "exempt", "Exempt"


class ContributionRule(OrganizationScopedModel):
    """
    Defines how a member contributes to event obligations.
    Referenced by Member (direct override) and by membership tier defaults.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    contribution_type = models.CharField(max_length=10, choices=ContributionType.choices, default=ContributionType.FULL)
    # For PARTIAL: either a fraction (0 < fraction <= 1) or a fixed cap (cents)
    fraction = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    fixed_cap_cents = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "contribution_rule"

    def __str__(self):
        return f"{self.name} ({self.contribution_type})"

    def calculate_obligation_cents(self, full_amount_cents: int) -> int:
        if self.contribution_type == ContributionType.EXEMPT:
            return 0
        if self.contribution_type == ContributionType.FULL:
            return full_amount_cents
        # PARTIAL
        if self.fraction is not None:
            amount = int(float(self.fraction) * full_amount_cents)
        else:
            amount = full_amount_cents
        if self.fixed_cap_cents is not None:
            amount = min(amount, self.fixed_cap_cents)
        return amount


class Household(OrganizationScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Display name for this household.")
    primary_contact = models.ForeignKey(
        "Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_contact_for",
    )
    # Emergency contact info
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "household"

    def __str__(self):
        return self.name


class Member(OrganizationScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    # Amharic name for matching purposes
    first_name_am = models.CharField(max_length=100, blank=True)
    last_name_am = models.CharField(max_length=100, blank=True)
    # Alternative spellings / transliterations (space-separated)
    name_aliases = models.TextField(blank=True, help_text="Comma-separated alternate spellings for reconciliation matching.")

    household = models.ForeignKey(
        Household,
        on_delete=models.PROTECT,
        related_name="members",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=15, choices=MemberStatus.choices, default=MemberStatus.ACTIVE, db_index=True)
    tier = models.CharField(max_length=15, choices=MembershipTier.choices, default=MembershipTier.STANDARD)
    contribution_rule = models.ForeignKey(
        ContributionRule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    join_date = models.DateField()
    leave_date = models.DateField(null=True, blank=True)

    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    phone_whatsapp = models.CharField(max_length=30, blank=True)
    preferred_language = models.CharField(max_length=10, default="en", choices=[("en", "English"), ("am", "Amharic")])
    address = models.TextField(blank=True)

    # For offline payment matching
    payment_reference = models.CharField(
        max_length=50,
        blank=True,
        unique=True,
        null=True,
        help_text="Short code member includes in payment memo for auto-matching.",
    )

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "member"
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def display_names(self) -> list[str]:
        """All name variants used for fuzzy matching."""
        names = [self.get_full_name(), f"{self.last_name} {self.first_name}"]
        if self.first_name_am or self.last_name_am:
            names.append(f"{self.first_name_am} {self.last_name_am}".strip())
        if self.name_aliases:
            names.extend([a.strip() for a in self.name_aliases.split(",") if a.strip()])
        return [n for n in names if n.strip()]

    def effective_contribution_rule(self):
        return self.contribution_rule


class Relationship(models.TextChoices):
    SPOUSE = "spouse", "Spouse"
    CHILD = "child", "Child"
    PARENT = "parent", "Parent"
    SIBLING = "sibling", "Sibling"
    OTHER = "other", "Other"


class FamilyMember(TimeStampedModel):
    """
    A dependent or covered family member under a primary Member's plan.
    Not an association member themselves — covered for bereavement/event payouts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="family_members",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    first_name_am = models.CharField(max_length=100, blank=True)
    last_name_am = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=10, choices=Relationship.choices)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "family_member"
        ordering = ["relationship", "date_of_birth"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.relationship}) → {self.member}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        from datetime import date
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class HouseholdMembershipHistory(TimeStampedModel):
    """Append-only record of household membership changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="household_history")
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="member_history")
    joined_on = models.DateField()
    left_on = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "household_membership_history"
        ordering = ["-joined_on"]
