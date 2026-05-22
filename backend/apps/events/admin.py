from django.contrib import admin
from .models import Event, EventOverride


class EventOverrideInline(admin.TabularInline):
    model = EventOverride
    extra = 0
    readonly_fields = ["applied_by", "reason", "action", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "event_type", "affected_household", "event_date", "payout_amount_cents",
        "status", "approved_by", "contribution_deadline",
    ]
    list_filter = ["status", "event_type", "organization"]
    search_fields = ["description", "affected_household__name"]
    readonly_fields = [
        "id", "status", "submitted_by", "submitted_at",
        "approved_by", "approved_at", "created_at", "updated_at",
    ]
    date_hierarchy = "event_date"
    inlines = [EventOverrideInline]

    def has_delete_permission(self, request, obj=None):
        return False
