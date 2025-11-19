"""
URL configuration for RAG document management.
"""
from django.urls import path
from apps.bot.views.document_views import (
    DocumentUploadView,
    DocumentListView,
    DocumentDetailView,
    DocumentDeleteView,
    DocumentStatusView,
    DocumentChunkListView,
)

app_name = 'documents'

urlpatterns = [
    # Document upload
    path('upload', DocumentUploadView.as_view(), name='upload'),
    
    # Document list and detail
    path('', DocumentListView.as_view(), name='list'),
    path('<uuid:id>', DocumentDetailView.as_view(), name='detail'),
    path('<uuid:id>/status', DocumentStatusView.as_view(), name='status'),
    
    # Document chunks
    path('<uuid:document_id>/chunks', DocumentChunkListView.as_view(), name='chunks'),
]
