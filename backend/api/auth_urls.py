from django.urls import path
from .auth_views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    RefreshView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='api_register'),
    path('login/',    LoginView.as_view(),    name='api_login'),
    path('logout/',   LogoutView.as_view(),   name='api_logout'),
    path('refresh/',  RefreshView.as_view(), name='api_token_refresh'),
    path('me/',       MeView.as_view(),       name='api_me'),
    path(
        'password-reset/',
        PasswordResetRequestView.as_view(),
        name='api_password_reset',
    ),
    path(
        'password-reset/confirm/',
        PasswordResetConfirmView.as_view(),
        name='api_password_reset_confirm',
    ),
]
