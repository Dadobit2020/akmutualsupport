from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.me_profile, name="me_profile"),
    path("profile/update/", views.me_update_profile, name="me_update_profile"),
    path("balance/", views.me_balance, name="me_balance"),
    path("obligations/", views.me_obligations, name="me_obligations"),
    path("payments/", views.me_payments, name="me_payments"),
    path("payments/<uuid:payment_id>/receipt/", views.me_receipt, name="me_receipt"),
    path("statement/", views.me_statement, name="me_statement"),
]
