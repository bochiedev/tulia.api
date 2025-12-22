"""
Serializers for RAG document management.
"""
from rest_framework import serializers
from django.conf import settings

from apps.bot.models import Document, DocumentChunk


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Document model.
    """
    file = serializers.FileField(write_only=True, required=False)
    uploaded_by = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Document
        fields = [
            'id',
            'file_name',
            'file_type',
            'file_size',
            'status',
            'processing_progress',
            'error_message',
            'chunk_count',
            'total_tokens',
            'uploaded_by',
            'created_at',
            'processed_at',
            'file',  # write_only
        ]
        read_only_fields = [
            'id',
            'file_type',
            'file_size',
            'status',
            'processing_progress',
            'error_message',
            'chunk_count',
            'total_tokens',
            'created_at',
            'processed_at',
        ]
    
    def validate_file(self, value):
        """Validate uploaded file."""
        # Check file size
        if value.size > settings.MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                f"File size {value.size} bytes exceeds maximum "
                f"{settings.MAX_DOCUMENT_SIZE} bytes ({settings.MAX_DOCUMENT_SIZE // (1024*1024)}MB)"
            )
        
        # Check file type
        file_ext = value.name.split('.')[-1].lower()
        if file_ext not in settings.ALLOWED_DOCUMENT_TYPES:
            raise serializers.ValidationError(
                f"File type '.{file_ext}' not allowed. "
                f"Allowed types: {', '.join(settings.ALLOWED_DOCUMENT_TYPES)}"
            )
        
        return value
    
    def validate_file_name(self, value):
        """Validate file name."""
        if not value or not value.strip():
            raise serializers.ValidationError("File name cannot be empty")
        
        # Check file extension
        if '.' not in value:
            raise serializers.ValidationError("File name must have an extension")
        
        file_ext = value.split('.')[-1].lower()
        if file_ext not in settings.ALLOWED_DOCUMENT_TYPES:
            raise serializers.ValidationError(
                f"File type '.{file_ext}' not allowed. "
                f"Allowed types: {', '.join(settings.ALLOWED_DOCUMENT_TYPES)}"
            )
        
        return value


class DocumentChunkSerializer(serializers.ModelSerializer):
    """
    Serializer for DocumentChunk model.
    """
    document_name = serializers.CharField(source='document.file_name', read_only=True)
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id',
            'document',
            'document_name',
            'chunk_index',
            'content',
            'token_count',
            'page_number',
            'section',
            'embedding_model',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'document_name',
            'created_at',
        ]


class DocumentUploadSerializer(serializers.Serializer):
    """
    Serializer for document upload endpoint.
    """
    file = serializers.FileField(required=True)
    
    def validate_file(self, value):
        """Validate uploaded file."""
        # Check file size
        if value.size > settings.MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                f"File size exceeds maximum {settings.MAX_DOCUMENT_SIZE // (1024*1024)}MB"
            )
        
        # Check file type
        file_ext = value.name.split('.')[-1].lower()
        if file_ext not in settings.ALLOWED_DOCUMENT_TYPES:
            raise serializers.ValidationError(
                f"File type '.{file_ext}' not allowed. "
                f"Allowed types: {', '.join(settings.ALLOWED_DOCUMENT_TYPES)}"
            )
        
        return value


class DocumentStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for document status information.
    """
    progress_percentage = serializers.IntegerField(source='processing_progress', read_only=True)
    
    class Meta:
        model = Document
        fields = [
            'id',
            'file_name',
            'status',
            'progress_percentage',
            'chunk_count',
            'total_tokens',
            'error_message',
            'created_at',
            'processed_at',
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_name', 'title', 'content_type',
            'file_size', 'status', 'error_message', 'chunk_count',
            'created_at', 'processed_at'
        ]
