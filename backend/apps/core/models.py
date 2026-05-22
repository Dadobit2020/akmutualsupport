import uuid
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract base using UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class OrganizationScopedModel(TimeStampedModel):
    """Abstract base scoping every row to an organization (single-tenant now, multi-tenant ready)."""

    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        abstract = True
