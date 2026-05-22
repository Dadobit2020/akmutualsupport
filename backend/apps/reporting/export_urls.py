from django.urls import path
from .export_views import (
    export_members_csv,
    export_obligations_csv,
    export_payments_csv,
    export_ledger_csv,
    export_member_statement_pdf,
    export_outstanding_csv,
)

urlpatterns = [
    path("members/", export_members_csv, name="export_members"),
    path("obligations/", export_obligations_csv, name="export_obligations"),
    path("payments/", export_payments_csv, name="export_payments"),
    path("ledger/", export_ledger_csv, name="export_ledger"),
    path("outstanding/", export_outstanding_csv, name="export_outstanding"),
    path("members/<uuid:member_id>/statement/", export_member_statement_pdf, name="export_member_statement"),
]
