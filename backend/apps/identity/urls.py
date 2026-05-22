from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView,
    CurrentUserView,
    mfa_setup_initiate,
    mfa_setup_confirm,
    mfa_disable,
    change_password,
    invite_user,
    set_password,
)

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("mfa/setup/", mfa_setup_initiate, name="mfa_setup_initiate"),
    path("mfa/confirm/", mfa_setup_confirm, name="mfa_setup_confirm"),
    path("mfa/disable/", mfa_disable, name="mfa_disable"),
    path("change-password/", change_password, name="change_password"),
    path("invite/", invite_user, name="invite_user"),
    path("set-password/", set_password, name="set_password"),
]
