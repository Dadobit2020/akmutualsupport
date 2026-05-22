"""
OrganizationMiddleware

Attaches the active Organization to every authenticated request as
`request.organization`. For v1 (single-tenant) this is always the one
organization that exists. When Phase 3 multi-tenancy is added, this
middleware is the single place to resolve the tenant from the request
(subdomain, header, or JWT claim) — no view code needs to change.

Resolution order:
  1. X-Organization-Slug header (for future multi-tenant clients)
  2. The user's first active org role (current single-tenant path)
  3. None (unauthenticated or no role — the view's permission class rejects it)
"""
from django.utils.functional import SimpleLazyObject


def _get_organization(request):
    if not request.user or not request.user.is_authenticated:
        return None

    slug = request.headers.get("X-Organization-Slug")
    from apps.identity.models import Organization, UserOrganizationRole

    if slug:
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            # Verify user has a role in this org (or is a superuser)
            if request.user.is_superuser:
                return org
            if UserOrganizationRole.objects.filter(
                user=request.user, organization=org, is_active=True
            ).exists():
                return org
            return None
        except Organization.DoesNotExist:
            return None

    # Single-tenant path: return the org the user belongs to
    if request.user.is_superuser:
        return Organization.objects.filter(is_active=True).first()

    role = (
        UserOrganizationRole.objects.filter(user=request.user, is_active=True)
        .select_related("organization")
        .first()
    )
    if role:
        return role.organization
    return None


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lazy so we only hit the DB if a view actually reads request.organization
        request.organization = SimpleLazyObject(lambda: _get_organization(request))
        return self.get_response(request)
