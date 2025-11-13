"""
URL routing for authentication endpoints.
"""
from django.urls import path
from apps.rbac.views_auth import (
    RegistrationView, LoginView, LogoutView, EmailVerificationView,
    ForgotPasswordView, ResetPasswordView, RefreshTokenView,
    UserProfileView
)

app_name = 'auth'

urlpatterns = [
    # Registration and login
    path('register', RegistrationView.as_view(), name='register'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    
    # Email verification
    path('verify-email', EmailVerificationView.as_view(), name='verify-email'),
    
    # Password reset
    path('forgot-password', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password', ResetPasswordView.as_view(), name='reset-password'),
    
    # Token refresh
    path('refresh-token', RefreshTokenView.as_view(), name='refresh-token'),
    
    # User profile (GET and PUT on same endpoint)
    path('me', UserProfileView.as_view(), name='profile'),
]
