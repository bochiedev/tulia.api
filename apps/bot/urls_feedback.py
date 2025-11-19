"""
URL configuration for feedback collection API.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.bot.views_feedback import (
    FeedbackSubmitView,
    FeedbackViewSet,
    HumanCorrectionViewSet,
)

router = DefaultRouter()
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'corrections', HumanCorrectionViewSet, basename='corrections')

urlpatterns = [
    path('feedback/submit/', FeedbackSubmitView.as_view(), name='feedback-submit'),
    path('', include(router.urls)),
]
