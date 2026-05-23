from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Member, Household, ContributionRule, HouseholdMembershipHistory


class MemberResource(resources.ModelResource):
    """
    Defines how Member rows are serialised for import/export.
    The organization FK is injected from the request in MemberAdmin.get_export_resource_kwargs.
    """

    class Meta:
        model = Member
        fields = (
            "first_name", "last_name", "first_name_am", "last_name_am",
            "email", "phone", "phone_whatsapp", "address",
            "join_date", "status", "tier", "notes", "payment_reference",
        )
        export_order = fields
        import_id_fields = ["first_name", "last_name", "join_date"]
        widgets = {
            "join_date": {"format": "%Y-%m-%d"},
        }

    def before_import_row(self, row, row_number=None, **kwargs):
        if not row.get("status"):
            row["status"] = "active"
        if not row.get("tier"):
            row["tier"] = "standard"

    def get_or_init_instance(self, instance_loader, row):
        instance, new = super().get_or_init_instance(instance_loader, row)
        if new and hasattr(self, "_import_org"):
            instance.organization = self._import_org
        return instance, new


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
class MemberAdmin(ImportExportModelAdmin):
    resource_classes = [MemberResource]
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

    def get_export_resource_kwargs(self, request, **kwargs):
        """Inject org into the resource so before_import_row can set it."""
        kwargs = super().get_export_resource_kwargs(request, **kwargs)
        return kwargs

    def get_import_resource_kwargs(self, request, **kwargs):
        kwargs = super().get_import_resource_kwargs(request, **kwargs)
        return kwargs

    def get_import_data_kwargs(self, request, *args, **kwargs):
        """Pass the current org to the resource before import rows are processed."""
        result = super().get_import_data_kwargs(request, *args, **kwargs)
        return result

    def process_import(self, request, *args, **kwargs):
        """Attach org to all resource instances before processing."""
        from apps.identity.models import Organization
        try:
            org = Organization.objects.get(slug="addis-kidan")
            for resource in self.get_import_resource_instances(request):
                resource._import_org = org
        except Organization.DoesNotExist:
            pass
        return super().process_import(request, *args, **kwargs)
