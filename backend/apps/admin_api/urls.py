from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="admin-dashboard"),
    path("members/", views.members_list, name="admin-members-list"),
    path("members/<uuid:member_id>/", views.member_detail, name="admin-member-detail"),
    path("payments/", views.payments_list, name="admin-payments-list"),
    path("obligations/", views.obligations_list, name="admin-obligations-list"),
    path("obligations/<uuid:obligation_id>/", views.obligation_detail, name="admin-obligation-detail"),
    path("obligations/send-reminders/", views.send_reminders, name="admin-send-reminders"),
    path("events/", views.events_list, name="admin-events-list"),
    path("settings/", views.org_settings, name="admin-settings"),
    path("assessment/preview/", views.assessment_preview, name="admin-assessment-preview"),
    path("assessment/process/", views.process_assessment, name="admin-process-assessment"),
    path("members/<uuid:member_id>/family/", views.family_members_list, name="admin-family-list"),
    path("members/<uuid:member_id>/family/<uuid:fm_id>/", views.family_member_detail, name="admin-family-detail"),
    path("obligations/generate-annual-dues/", views.generate_annual_dues, name="admin-generate-dues"),
    path("obligations/bulk-delete-dues/", views.bulk_delete_dues, name="admin-bulk-delete-dues"),
    path("obligations/reset-deadline/", views.reset_dues_deadline, name="admin-reset-deadline"),
    path("payouts/", views.payouts_list, name="admin-payouts"),
    path("import/parse/", views.statement_parse, name="admin-import-parse"),
    path("import/process/", views.statement_process, name="admin-import-process"),
]
