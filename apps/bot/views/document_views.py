"""
API views for RAG document management.
"""
import logging
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.permissions import HasTenantScopes
from apps.bot.models import Document, DocumentChunk
from apps.bot.serializers.document_serializers import (
    DocumentSerializer,
    DocumentChunkSerializer,
    DocumentUploadSerializer,
    DocumentStatusSerializer
)
from apps.bot.services.document_store_service import DocumentStoreService

logger = logging.getLogger(__name__)


class DocumentUploadView(APIView):
    """
    Upload a document for RAG processing.
    
    Required scope: integrations:manage
    
    POST /v1/documents/upload
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """
        Upload a document.
        
        Request:
            - file: Document file (PDF or TXT, max 10MB)
        
        Response:
            - 201: Document uploaded successfully
            - 400: Invalid file or validation error
            - 403: Missing required scope
        """
        serializer = DocumentUploadSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = serializer.validated_data['file']
        
        try:
            # Upload document using service
            document_service = DocumentStoreService.create_for_tenant(
                request.tenant
            )
            
            document = document_service.upload_document(
                file=file,
                file_name=file.name,
                uploaded_by=request.user.email if request.user else None
            )
            
            # Trigger async processing
            from apps.bot.tasks import process_document
            process_document.delay(str(document.id))
            
            logger.info(
                f"Document uploaded: {document.id} by tenant {request.tenant.id}"
            )
            
            return Response(
                DocumentSerializer(document).data,
                status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            logger.error(f"Document upload validation error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Document upload error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to upload document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentListView(generics.ListAPIView):
    """
    List all documents for the tenant.
    
    Required scope: integrations:manage
    
    GET /v1/documents
    
    Query parameters:
        - status: Filter by status (pending, processing, completed, failed)
        - file_type: Filter by file type (pdf, txt)
        - search: Search by file name
        - ordering: Order by field (created_at, file_name, status)
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    serializer_class = DocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'file_type']
    search_fields = ['file_name']
    ordering_fields = ['created_at', 'file_name', 'status', 'file_size']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get documents for current tenant."""
        return Document.objects.filter(
            tenant=self.request.tenant
        ).order_by('-created_at')


class DocumentDetailView(generics.RetrieveAPIView):
    """
    Get document details.
    
    Required scope: integrations:manage
    
    GET /v1/documents/{id}
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    serializer_class = DocumentSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        """Get documents for current tenant."""
        return Document.objects.filter(tenant=self.request.tenant)


class DocumentDeleteView(generics.DestroyAPIView):
    """
    Delete a document and its chunks.
    
    Required scope: integrations:manage
    
    DELETE /v1/documents/{id}
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    lookup_field = 'id'
    
    def get_queryset(self):
        """Get documents for current tenant."""
        return Document.objects.filter(tenant=self.request.tenant)
    
    def perform_destroy(self, instance):
        """Delete document using service."""
        try:
            document_service = DocumentStoreService.create_for_tenant(
                self.request.tenant
            )
            document_service.delete_document(str(instance.id))
            
            logger.info(
                f"Document deleted: {instance.id} by tenant {self.request.tenant.id}"
            )
        except Exception as e:
            logger.error(f"Document deletion error: {e}", exc_info=True)
            raise


class DocumentStatusView(APIView):
    """
    Get document processing status.
    
    Required scope: integrations:manage
    
    GET /v1/documents/{id}/status
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    
    def get(self, request, id):
        """
        Get document status.
        
        Response:
            - 200: Status information
            - 404: Document not found
            - 403: Missing required scope
        """
        try:
            document = Document.objects.get(
                id=id,
                tenant=request.tenant
            )
            
            return Response(
                DocumentStatusSerializer(document).data,
                status=status.HTTP_200_OK
            )
            
        except Document.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentChunkListView(generics.ListAPIView):
    """
    List chunks for a document.
    
    Required scope: integrations:manage
    
    GET /v1/documents/{document_id}/chunks
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    serializer_class = DocumentChunkSerializer
    
    def get_queryset(self):
        """Get chunks for document."""
        document_id = self.kwargs.get('document_id')
        
        return DocumentChunk.objects.filter(
            document_id=document_id,
            tenant=self.request.tenant
        ).order_by('chunk_index')
