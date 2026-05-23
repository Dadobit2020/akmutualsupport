from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="admin-dashboard"),
    path("members/", views.members_list, name="admin-members-list"),
    path("members/<uuid:member_id>/", views.member_detail, name="admin-member-detail"),
    path("payments/", views.payments_list, name="admin-payments-list"),
    path("obligations/", views.obligations_list, name="admin-obligations-list"),
    path("obligations/send-reminders/", views.send_reminders, name="admin-send-reminders"),
    path("events/", views.events_list, name="admin-events-list"),
    path("settings/", views.org_settings, name="admin-settings"),
    path("assessment/preview/", views.assessment_preview, name="admin-assessment-preview"),
    path("assessment/process/", views.process_assessment, name="admin-process-assessment"),
    path("members/<uuid:member_id>/family/", views.family_members_list, name="admin-family-list"),
    path("members/<uuid:member_id>/family/<uuid:fm_id>/", views.family_member_detail, name="admin-family-detail"),
]
