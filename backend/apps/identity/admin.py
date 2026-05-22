from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, UserOrganizationRole


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "currency", "is_active", "created_at"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "is_active", "is_staff", "mfa_enabled"]
    list_filter = ["is_active", "is_staff", "mfa_enabled"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "member")}),
        ("MFA", {"fields": ("mfa_enabled", "mfa_secret")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ["created_at", "updated_at"]
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2"),
        }),
    )


@admin.register(UserOrganizationRole)
class UserOrganizationRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active", "organization"]
    search_fields = ["user__email"]
