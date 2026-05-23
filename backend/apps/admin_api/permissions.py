from rest_framework.permissions import BasePermission
from apps.identity.models import UserOrganizationRole, Role


class IsOrgAdmin(BasePermission):
    """
    Allows access to users with an admin-level role (super_admin, treasurer,
    secretary, or chairperson) within the current request organisation.
    Django superusers always pass.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        org = getattr(request, "organization", None)
        if not org:
            return False
        admin_roles = {
            Role.SUPER_ADMIN,
            Role.TREASURER,
            Role.SECRETARY,
            Role.CHAIRPERSON,
        }
        return UserOrganizationRole.objects.filter(
            user=request.user,
            organization=org,
            role__in=admin_roles,
            is_active=True,
        ).exists()
