from django.contrib import admin
from .models import LedgerAccount, LedgerTransaction, LedgerEntry


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    readonly_fields = ["id", "account", "debit_cents", "credit_cents", "description", "member", "obligation", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "account_type", "organization", "is_active"]
    list_filter = ["account_type", "organization"]


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = ["transaction_date", "description", "source", "posted_by", "organization"]
    list_filter = ["source", "organization"]
    search_fields = ["description"]
    readonly_fields = ["id", "created_at", "updated_at", "reverses"]
    inlines = [LedgerEntryInline]
    date_hierarchy = "transaction_date"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
