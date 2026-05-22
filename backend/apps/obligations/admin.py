from django.contrib import admin
from .models import Obligation, Payment, PaymentApplication


class PaymentApplicationInline(admin.TabularInline):
    model = PaymentApplication
    extra = 0
    readonly_fields = ["obligation", "applied_cents"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Obligation)
class ObligationAdmin(admin.ModelAdmin):
    list_display = ["member", "event", "amount_cents", "paid_cents", "outstanding_cents_display", "due_date", "status"]
    list_filter = ["status", "obligation_type", "organization"]
    search_fields = ["member__first_name", "member__last_name"]
    readonly_fields = ["id", "paid_cents", "created_at", "updated_at"]
    date_hierarchy = "due_date"

    def outstanding_cents_display(self, obj):
        return obj.outstanding_cents
    outstanding_cents_display.short_description = "Outstanding (¢)"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["member", "amount_cents", "payment_date", "method", "reference", "organization"]
    list_filter = ["method", "organization"]
    search_fields = ["member__first_name", "member__last_name", "reference"]
    readonly_fields = ["id", "imported_transaction", "ledger_transaction", "created_at"]
    inlines = [PaymentApplicationInline]

    def has_delete_permission(self, request, obj=None):
        return False
