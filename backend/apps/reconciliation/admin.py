from django.contrib import admin
from .models import ImportBatch, ImportedTransaction


class ImportedTransactionInline(admin.TabularInline):
    model = ImportedTransaction
    extra = 0
    readonly_fields = [
        "transaction_date", "amount_cents", "payer_name", "match_status",
        "confidence_score", "matched_member", "match_explanation",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "source", "status", "row_count", "matched_count", "applied_count", "created_at"]
    list_filter = ["status", "source", "organization"]
    readonly_fields = ["id", "file", "row_count", "matched_count", "applied_count", "status", "created_at"]
    inlines = [ImportedTransactionInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImportedTransaction)
class ImportedTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "transaction_date", "payer_name", "amount_cents",
        "match_status", "confidence_score", "matched_member",
    ]
    list_filter = ["match_status", "organization", "batch__source"]
    search_fields = ["payer_name", "memo", "source_reference"]
    readonly_fields = [
        "id", "batch", "fingerprint", "match_explanation",
        "confidence_score", "reviewed_by", "reviewed_at", "created_at",
    ]

    def has_delete_permission(self, request, obj=None):
        return False
