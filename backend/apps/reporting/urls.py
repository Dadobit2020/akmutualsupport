from django.urls import path
from .views import dashboard, outstanding_balances

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("outstanding-balances/", outstanding_balances, name="outstanding_balances"),
]
