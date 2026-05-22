from rest_framework.permissions import BasePermission
from .models import Role, UserOrganizationRole


def get_user_roles(user, organization):
    return set(
        UserOrganizationRole.objects.filter(
            user=user,
            organization=organization,
            is_active=True,
        ).values_list("role", flat=True)
    )


def has_role(user, organization, *roles):
    if user.is_superuser:
        return True
    return bool(get_user_roles(user, organization) & set(roles))


class IsAdminRole(BasePermission):
    """Treasurer, Secretary, Chairperson, or Super Admin."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if not org:
            return False
        return has_role(
            request.user,
            org,
            Role.SUPER_ADMIN,
            Role.TREASURER,
            Role.SECRETARY,
            Role.CHAIRPERSON,
        )


class IsTreasurer(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if not org:
            return False
        return has_role(request.user, org, Role.TREASURER, Role.SUPER_ADMIN)


class IsChairperson(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if not org:
            return False
        return has_role(request.user, org, Role.CHAIRPERSON, Role.SUPER_ADMIN)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser
            or has_role(request.user, getattr(request, "organization", None), Role.SUPER_ADMIN)
        )
