from django.contrib import admin
from .models import MessageTemplate, Communication


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "channel", "is_active", "organization"]
    list_filter = ["channel", "is_active"]


@admin.register(Communication)
class CommunicationAdmin(admin.ModelAdmin):
    list_display = ["recipient_address", "channel", "subject", "status", "sent_at", "created_at"]
    list_filter = ["channel", "status"]
    search_fields = ["recipient_address", "subject"]
    readonly_fields = ["id", "sent_at", "provider_message_id", "error_message", "created_at"]

    def has_delete_permission(self, request, obj=None):
        return False
