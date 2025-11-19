# Document Management API Guide

Quick reference for using the RAG document management API.

## Endpoints

### Upload Document
```http
POST /v1/bot/documents/upload
Content-Type: multipart/form-data
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}

file: <binary>
```

**Scope Required:** `integrations:manage`

**Limits:**
- Max file size: 10MB
- Allowed types: PDF, TXT

**Response:**
```json
{
  "id": "uuid",
  "file_name": "document.pdf",
  "status": "pending",
  "file_type": "pdf",
  "file_size": 245760
}
```

### List Documents
```http
GET /v1/bot/documents/?status=completed&search=faq
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}
```

**Query Parameters:**
- `status`: pending, processing, completed, failed
- `file_type`: pdf, txt
- `search`: Search by file name
- `ordering`: created_at, file_name, status, file_size

### Get Document
```http
GET /v1/bot/documents/{id}
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}
```

### Delete Document
```http
DELETE /v1/bot/documents/{id}
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}
```

**Note:** Deletes document, all chunks, and vectors from vector store.

### Get Processing Status
```http
GET /v1/bot/documents/{id}/status
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "file_name": "document.pdf",
  "status": "processing",
  "progress_percentage": 45,
  "chunk_count": 10,
  "total_tokens": 2500,
  "error_message": null
}
```

### List Document Chunks
```http
GET /v1/bot/documents/{document_id}/chunks
X-TENANT-ID: {tenant_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "chunk_index": 0,
      "content": "Chunk text...",
      "token_count": 150,
      "page_number": 1,
      "section": "Introduction"
    }
  ]
}
```

## Python Client Example

```python
import requests

class DocumentClient:
    def __init__(self, base_url, tenant_id, api_key):
        self.base_url = base_url
        self.headers = {
            'X-TENANT-ID': tenant_id,
            'X-TENANT-API-KEY': api_key
        }
    
    def upload(self, file_path):
        """Upload a document."""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f'{self.base_url}/v1/bot/documents/upload',
                headers=self.headers,
                files=files
            )
        return response.json()
    
    def list(self, status=None, search=None):
        """List documents."""
        params = {}
        if status:
            params['status'] = status
        if search:
            params['search'] = search
        
        response = requests.get(
            f'{self.base_url}/v1/bot/documents/',
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def get_status(self, document_id):
        """Get document processing status."""
        response = requests.get(
            f'{self.base_url}/v1/bot/documents/{document_id}/status',
            headers=self.headers
        )
        return response.json()
    
    def delete(self, document_id):
        """Delete a document."""
        response = requests.delete(
            f'{self.base_url}/v1/bot/documents/{document_id}',
            headers=self.headers
        )
        return response.status_code == 204

# Usage
client = DocumentClient(
    base_url='https://api.example.com',
    tenant_id='your-tenant-id',
    api_key='your-api-key'
)

# Upload
doc = client.upload('business_faq.pdf')
print(f"Uploaded: {doc['id']}")

# Check status
status = client.get_status(doc['id'])
print(f"Status: {status['status']} ({status['progress_percentage']}%)")

# List completed documents
docs = client.list(status='completed')
print(f"Found {docs['count']} documents")
```

## Error Handling

### 400 Bad Request
- File too large (>10MB)
- Invalid file type
- Missing file

### 401 Unauthorized
- Missing or invalid authentication

### 403 Forbidden
- Missing `integrations:manage` scope

### 404 Not Found
- Document doesn't exist
- Document belongs to different tenant

### 500 Internal Server Error
- Processing failure
- Storage failure

## Processing Pipeline

1. **Upload** → Document created with `status=pending`
2. **Queue** → Celery task scheduled
3. **Extract** → Text extracted from PDF/TXT
4. **Chunk** → Content split into chunks (300-500 tokens)
5. **Embed** → Embeddings generated for each chunk
6. **Index** → Vectors stored in Pinecone
7. **Complete** → `status=completed`, chunks available

**Average Processing Time:**
- Small documents (<1MB): 10-30 seconds
- Medium documents (1-5MB): 30-90 seconds
- Large documents (5-10MB): 90-180 seconds

## Best Practices

### Document Organization
- Use descriptive file names
- Group related documents by topic
- Keep documents focused (single topic per document)
- Update documents when information changes

### File Preparation
- Use text-based PDFs (not scanned images)
- Ensure good formatting and structure
- Remove unnecessary pages
- Keep file sizes reasonable (<5MB ideal)

### Monitoring
- Check processing status after upload
- Monitor for failed documents
- Review error messages
- Track chunk counts for quality

### Performance
- Upload during off-peak hours for large batches
- Use async processing (don't wait for completion)
- Cache frequently accessed documents
- Delete unused documents to save storage

## Troubleshooting

### Document Stuck in "Processing"
- Check Celery worker logs
- Verify Redis connection
- Check vector store connectivity
- Restart processing task if needed

### "Failed" Status
- Check `error_message` field
- Common causes:
  - Corrupted PDF
  - Scanned image (no text)
  - Unsupported PDF version
  - Vector store connection failure

### Slow Processing
- Large file size
- Complex PDF structure
- High system load
- Vector store latency

### Search Not Finding Content
- Document may not be indexed yet
- Check document status is "completed"
- Verify chunks were created
- Check vector store connection

## Support

For issues or questions:
- Check logs: `apps/bot/services/document_store_service.py`
- Review tests: `apps/bot/tests/test_document_api.py`
- See implementation: `apps/bot/views/document_views.py`
