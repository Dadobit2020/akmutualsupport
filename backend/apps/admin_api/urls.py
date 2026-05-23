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
]
