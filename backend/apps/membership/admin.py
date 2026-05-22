from django.contrib import admin
from .models import Member, Household, ContributionRule, HouseholdMembershipHistory


@admin.register(ContributionRule)
class ContributionRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "contribution_type", "fraction", "fixed_cap_cents", "is_active"]
    list_filter = ["contribution_type", "is_active", "organization"]


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ["name", "primary_contact", "organization"]
    search_fields = ["name"]
    raw_id_fields = ["primary_contact"]


class HouseholdMembershipInline(admin.TabularInline):
    model = HouseholdMembershipHistory
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        "last_name", "first_name", "household", "status", "tier",
        "email", "phone", "join_date", "organization",
    ]
    list_filter = ["status", "tier", "organization"]
    search_fields = ["first_name", "last_name", "email", "phone", "payment_reference"]
    raw_id_fields = ["household", "contribution_rule"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [HouseholdMembershipInline]
    fieldsets = (
        ("Identity", {"fields": ("first_name", "last_name", "first_name_am", "last_name_am", "name_aliases")}),
        ("Membership", {"fields": ("organization", "household", "status", "tier", "contribution_rule", "join_date", "leave_date")}),
        ("Contact", {"fields": ("email", "phone", "phone_whatsapp", "address", "preferred_language")}),
        ("Reconciliation", {"fields": ("payment_reference",)}),
        ("Notes", {"fields": ("notes",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
