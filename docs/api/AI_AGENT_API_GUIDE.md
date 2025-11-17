# AI Agent API Guide

## Overview

The AI Agent API provides comprehensive endpoints for configuring and managing the AI-powered customer service agent. This includes agent configuration, knowledge base management, interaction tracking, and analytics.

All endpoints require proper authentication via `X-TENANT-ID` and `X-TENANT-API-KEY` headers and enforce RBAC (Role-Based Access Control) using scope-based permissions.

## Base URL

```
https://api.tulia.ai/v1/bot
```

## Authentication

All requests must include the following headers:

```http
X-TENANT-ID: <your-tenant-id>
X-TENANT-API-KEY: <your-api-key>
Content-Type: application/json
```

## RBAC Requirements

Different endpoints require different permission scopes:

- **Agent Configuration**: `integrations:manage`
- **Knowledge Base Management**: `integrations:manage`
- **Analytics & Interactions**: `analytics:view`

## Table of Contents

1. [Agent Configuration](#agent-configuration)
2. [Knowledge Base Management](#knowledge-base-management)
3. [Agent Interactions](#agent-interactions)
4. [Analytics](#analytics)
5. [Error Handling](#error-handling)
6. [Rate Limits](#rate-limits)

---

## Agent Configuration

### Get Agent Configuration

Retrieve the current AI agent configuration for your tenant.

**Endpoint:** `GET /v1/bot/agent-config`

**Required Scope:** `integrations:manage`

**Response:**

```json
{
  "id": "uuid",
  "tenant": "uuid",
  "tenant_name": "My Business",
  "agent_name": "Sarah",
  "personality_traits": {
    "helpful": true,
    "empathetic": true,
    "professional": true
  },
  "tone": "friendly",
  "default_model": "gpt-4o",
  "fallback_models": ["gpt-4o-mini"],
  "temperature": 0.7,
  "max_response_length": 500,
  "behavioral_restrictions": ["no medical advice", "no legal advice"],
  "required_disclaimers": ["I'm an AI assistant"],
  "confidence_threshold": 0.7,
  "auto_handoff_topics": ["refunds", "complaints"],
  "max_low_confidence_attempts": 2,
  "enable_proactive_suggestions": true,
  "enable_spelling_correction": true,
  "enable_rich_messages": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Example Request:**

```bash
curl -X GET https://api.tulia.ai/v1/bot/agent-config \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Update Agent Configuration

Update the AI agent configuration. Supports partial updates.

**Endpoint:** `PUT /v1/bot/agent-config`

**Required Scope:** `integrations:manage`

**Rate Limit:** 5 requests per minute

**Request Body:**

```json
{
  "agent_name": "Sarah",
  "tone": "friendly",
  "default_model": "gpt-4o",
  "temperature": 0.7,
  "confidence_threshold": 0.75,
  "enable_proactive_suggestions": true
}
```

**Response:** Same as GET response

**Example Request:**

```bash
curl -X PUT https://api.tulia.ai/v1/bot/agent-config \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Sarah",
    "tone": "friendly",
    "default_model": "gpt-4o",
    "confidence_threshold": 0.75
  }'
```

**Configuration Fields:**

| Field | Type | Description | Valid Values |
|-------|------|-------------|--------------|
| `agent_name` | string | Name of the AI agent | Any string (max 100 chars) |
| `personality_traits` | object | Personality characteristics | JSON object |
| `tone` | string | Communication tone | `professional`, `friendly`, `casual`, `formal` |
| `default_model` | string | Primary AI model | `gpt-4o`, `gpt-4o-mini`, `o1-preview`, `o1-mini` |
| `fallback_models` | array | Backup models | Array of model names |
| `temperature` | float | Response creativity | 0.0 - 2.0 |
| `max_response_length` | integer | Max response characters | 50 - 2000 |
| `behavioral_restrictions` | array | Topics to avoid | Array of strings |
| `required_disclaimers` | array | Required disclaimers | Array of strings |
| `confidence_threshold` | float | Handoff threshold | 0.0 - 1.0 |
| `auto_handoff_topics` | array | Auto-escalate topics | Array of strings |
| `max_low_confidence_attempts` | integer | Attempts before handoff | 1 - 10 |
| `enable_proactive_suggestions` | boolean | Enable suggestions | true/false |
| `enable_spelling_correction` | boolean | Enable spell check | true/false |
| `enable_rich_messages` | boolean | Enable rich WhatsApp messages | true/false |

---

## Knowledge Base Management

### List Knowledge Entries

Retrieve all knowledge base entries with optional filtering.

**Endpoint:** `GET /v1/bot/knowledge`

**Required Scope:** `integrations:manage`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `entry_type` | string | Filter by type: `faq`, `policy`, `product_info`, `service_info`, `procedure`, `general` |
| `category` | string | Filter by category |
| `is_active` | string | Filter by status: `true`, `false`, `all` (default: `true`) |
| `page` | integer | Page number |
| `page_size` | integer | Items per page (max 100) |

**Response:**

```json
{
  "count": 50,
  "next": "https://api.tulia.ai/v1/bot/knowledge?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "tenant": "uuid",
      "tenant_name": "My Business",
      "entry_type": "faq",
      "category": "general",
      "title": "What are your business hours?",
      "content": "We are open Monday-Friday 9am-5pm EST.",
      "keywords": "hours,schedule,open",
      "keywords_list": ["hours", "schedule", "open"],
      "metadata": {},
      "priority": 80,
      "is_active": true,
      "version": 1,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/knowledge?entry_type=faq&page=1" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Create Knowledge Entry

Create a new knowledge base entry.

**Endpoint:** `POST /v1/bot/knowledge`

**Required Scope:** `integrations:manage`

**Rate Limit:** 10 requests per minute

**Request Body:**

```json
{
  "entry_type": "faq",
  "title": "What are your business hours?",
  "content": "We are open Monday-Friday 9am-5pm EST.",
  "category": "general",
  "keywords_list": ["hours", "schedule", "open"],
  "priority": 80,
  "is_active": true,
  "metadata": {}
}
```

**Response:** Same as list entry format

**Example Request:**

```bash
curl -X POST https://api.tulia.ai/v1/bot/knowledge \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_type": "faq",
    "title": "What are your business hours?",
    "content": "We are open Monday-Friday 9am-5pm EST.",
    "category": "general",
    "keywords_list": ["hours", "schedule", "open"],
    "priority": 80
  }'
```

### Get Knowledge Entry

Retrieve a specific knowledge entry by ID.

**Endpoint:** `GET /v1/bot/knowledge/{id}`

**Required Scope:** `integrations:manage`

**Response:** Same as list entry format

**Example Request:**

```bash
curl -X GET https://api.tulia.ai/v1/bot/knowledge/{id} \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Update Knowledge Entry

Update an existing knowledge entry (full or partial update).

**Endpoint:** `PUT /v1/bot/knowledge/{id}` (full update)  
**Endpoint:** `PATCH /v1/bot/knowledge/{id}` (partial update)

**Required Scope:** `integrations:manage`

**Request Body:** Same as create (all fields for PUT, subset for PATCH)

**Response:** Updated entry

**Example Request:**

```bash
curl -X PATCH https://api.tulia.ai/v1/bot/knowledge/{id} \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"priority": 95}'
```

### Delete Knowledge Entry

Soft delete a knowledge entry (sets `is_active=false`).

**Endpoint:** `DELETE /v1/bot/knowledge/{id}`

**Required Scope:** `integrations:manage`

**Response:** 204 No Content

**Example Request:**

```bash
curl -X DELETE https://api.tulia.ai/v1/bot/knowledge/{id} \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Search Knowledge Base

Search knowledge base using semantic similarity.

**Endpoint:** `GET /v1/bot/knowledge/search`

**Required Scope:** `integrations:manage`

**Rate Limit:** 60 requests per minute

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query |
| `entry_type` | string | No | Filter by type (comma-separated) |
| `limit` | integer | No | Max results (1-20, default: 5) |
| `min_similarity` | float | No | Min similarity score (0.0-1.0, default: 0.7) |

**Response:**

```json
[
  {
    "entry": {
      "id": "uuid",
      "title": "What are your business hours?",
      "content": "We are open Monday-Friday 9am-5pm EST.",
      ...
    },
    "similarity_score": 0.92
  }
]
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/knowledge/search?q=business%20hours&limit=5" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Bulk Import Knowledge Entries

Import multiple knowledge entries at once (JSON or CSV).

**Endpoint:** `POST /v1/bot/knowledge/bulk-import`

**Required Scope:** `integrations:manage`

**Request Body (JSON):**

```json
{
  "entries": [
    {
      "entry_type": "faq",
      "title": "Question 1",
      "content": "Answer 1",
      "category": "general",
      "keywords_list": ["keyword1"],
      "priority": 50
    },
    {
      "entry_type": "policy",
      "title": "Policy 1",
      "content": "Policy details",
      "priority": 80
    }
  ]
}
```

**Request Body (CSV):**

CSV with columns: `entry_type`, `title`, `content`, `category`, `keywords`, `priority`, `is_active`

**Response:**

```json
{
  "success_count": 2,
  "error_count": 0,
  "errors": [],
  "created_ids": ["uuid1", "uuid2"]
}
```

**Example Request (JSON):**

```bash
curl -X POST https://api.tulia.ai/v1/bot/knowledge/bulk-import \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {
        "entry_type": "faq",
        "title": "Question 1",
        "content": "Answer 1",
        "keywords_list": ["keyword1"],
        "priority": 50
      }
    ]
  }'
```

**Example Request (CSV):**

```bash
curl -X POST https://api.tulia.ai/v1/bot/knowledge/bulk-import \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>" \
  -H "Content-Type: text/csv" \
  --data-binary @knowledge_entries.csv
```

---

## Agent Interactions

### List Agent Interactions

Retrieve all AI agent interactions with filtering.

**Endpoint:** `GET /v1/bot/interactions`

**Required Scope:** `analytics:view`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string | Filter by conversation |
| `model_used` | string | Filter by model name |
| `handoff_triggered` | string | Filter by handoff status (`true`/`false`) |
| `min_confidence` | float | Minimum confidence score (0.0-1.0) |
| `max_confidence` | float | Maximum confidence score (0.0-1.0) |
| `start_date` | string | Start date (YYYY-MM-DD) |
| `end_date` | string | End date (YYYY-MM-DD) |
| `page` | integer | Page number |
| `page_size` | integer | Items per page (max 200) |

**Response:**

```json
{
  "count": 100,
  "next": "https://api.tulia.ai/v1/bot/interactions?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "conversation": "uuid",
      "tenant_name": "My Business",
      "model_used": "gpt-4o",
      "confidence_score": 0.85,
      "handoff_triggered": false,
      "message_type": "text",
      "estimated_cost": "0.001500",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/interactions?model_used=gpt-4o&page=1" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Get Agent Interaction Details

Retrieve detailed information about a specific interaction.

**Endpoint:** `GET /v1/bot/interactions/{id}`

**Required Scope:** `analytics:view`

**Response:**

```json
{
  "id": "uuid",
  "conversation": "uuid",
  "tenant_id": "uuid",
  "tenant_name": "My Business",
  "customer_phone": "+1234567890",
  "customer_message": "What are your hours?",
  "detected_intents": [
    {"intent": "business_hours", "confidence": 0.95}
  ],
  "intent_names": ["business_hours"],
  "primary_intent": "business_hours",
  "model_used": "gpt-4o",
  "context_size": 2500,
  "processing_time_ms": 1200,
  "agent_response": "We are open Monday-Friday 9am-5pm EST.",
  "confidence_score": 0.95,
  "handoff_triggered": false,
  "handoff_reason": "",
  "message_type": "text",
  "token_usage": {
    "prompt_tokens": 2000,
    "completion_tokens": 50,
    "total_tokens": 2050
  },
  "total_tokens": 2050,
  "estimated_cost": "0.001500",
  "cost_per_token": "0.000000732",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Example Request:**

```bash
curl -X GET https://api.tulia.ai/v1/bot/interactions/{id} \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Get Interaction Statistics

Get aggregated statistics about agent interactions.

**Endpoint:** `GET /v1/bot/interactions/stats`

**Required Scope:** `analytics:view`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | Start date (YYYY-MM-DD, default: 30 days ago) |
| `end_date` | string | End date (YYYY-MM-DD, default: today) |

**Response:**

```json
{
  "total_interactions": 1000,
  "total_cost": "15.500000",
  "avg_confidence": 0.850,
  "handoff_count": 50,
  "handoff_rate": 0.050,
  "interactions_by_model": {
    "gpt-4o": 800,
    "gpt-4o-mini": 200
  },
  "cost_by_model": {
    "gpt-4o": "14.000000",
    "gpt-4o-mini": "1.500000"
  },
  "interactions_by_type": {
    "text": 900,
    "button": 50,
    "list": 30,
    "media": 20
  },
  "high_confidence_count": 850,
  "low_confidence_count": 150,
  "avg_processing_time_ms": 1200.50,
  "avg_tokens": 2050.25
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/interactions/stats?start_date=2024-01-01" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

---

## Analytics

### Conversation Statistics

Get statistics about AI agent conversations.

**Endpoint:** `GET /v1/bot/analytics/conversations`

**Required Scope:** `analytics:view`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | Start date (YYYY-MM-DD, default: 30 days ago) |
| `end_date` | string | End date (YYYY-MM-DD, default: today) |

**Response:**

```json
{
  "total_interactions": 1000,
  "total_conversations": 250,
  "average_confidence": 0.850,
  "average_processing_time_ms": 1200.50,
  "high_confidence_rate": 0.850,
  "low_confidence_rate": 0.150,
  "message_type_distribution": {
    "text": 900,
    "button": 50,
    "list": 30,
    "media": 20
  },
  "model_usage": {
    "gpt-4o": 800,
    "gpt-4o-mini": 200
  },
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/analytics/conversations?start_date=2024-01-01" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Handoff Analytics

Get analytics about handoffs to human agents.

**Endpoint:** `GET /v1/bot/analytics/handoffs`

**Required Scope:** `analytics:view`

**Query Parameters:** Same as conversation statistics

**Response:**

```json
{
  "total_handoffs": 50,
  "handoff_rate": 0.050,
  "handoff_reasons": {
    "low_confidence": 25,
    "explicit_request": 15,
    "complex_issue": 10
  },
  "average_attempts_before_handoff": 2.5,
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/analytics/handoffs" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Cost Analytics

Get cost tracking analytics for AI agent usage.

**Endpoint:** `GET /v1/bot/analytics/costs`

**Required Scope:** `analytics:view`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | Start date (YYYY-MM-DD, default: 30 days ago) |
| `end_date` | string | End date (YYYY-MM-DD, default: today) |
| `group_by` | string | Group by: `day`, `week`, `month`, `model` (default: `model`) |

**Response:**

```json
{
  "total_tokens": 2050000,
  "total_cost": "15.500000",
  "average_cost_per_interaction": "0.015500",
  "cost_by_model": {
    "gpt-4o": {
      "total_tokens": 1640000,
      "total_cost": "14.000000",
      "interaction_count": 800,
      "average_cost_per_interaction": "0.017500"
    },
    "gpt-4o-mini": {
      "total_tokens": 410000,
      "total_cost": "1.500000",
      "interaction_count": 200,
      "average_cost_per_interaction": "0.007500"
    }
  },
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/analytics/costs?group_by=model" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

### Topic Analytics

Get analytics about common topics and intents.

**Endpoint:** `GET /v1/bot/analytics/topics`

**Required Scope:** `analytics:view`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | Start date (YYYY-MM-DD, default: 30 days ago) |
| `end_date` | string | End date (YYYY-MM-DD, default: today) |
| `limit` | integer | Max topics to return (1-50, default: 10) |

**Response:**

```json
{
  "common_intents": [
    {
      "intent": "business_hours",
      "count": 150,
      "percentage": 15.0
    },
    {
      "intent": "product_inquiry",
      "count": 120,
      "percentage": 12.0
    }
  ],
  "total_unique_intents": 25,
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.tulia.ai/v1/bot/analytics/topics?limit=10" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "X-TENANT-API-KEY: <api-key>"
```

---

## Error Handling

All endpoints return standard HTTP status codes and error responses:

### Success Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `204 No Content` - Resource deleted successfully

### Error Codes

- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Missing required RBAC scope
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "error": "Error message describing what went wrong"
}
```

### Validation Error Format

```json
{
  "field_name": [
    "Error message for this field"
  ]
}
```

---

## Rate Limits

Different endpoints have different rate limits:

| Endpoint | Rate Limit |
|----------|------------|
| `PUT /v1/bot/agent-config` | 5 requests/minute |
| `POST /v1/bot/knowledge` | 10 requests/minute |
| `GET /v1/bot/knowledge/search` | 60 requests/minute |
| All other endpoints | No specific limit (general API limits apply) |

When rate limit is exceeded, you'll receive a `429 Too Many Requests` response.

---

## Best Practices

### Agent Configuration

1. **Start with defaults**: Use the default configuration and adjust based on your needs
2. **Test temperature**: Lower values (0.3-0.5) for consistent responses, higher (0.7-0.9) for creative responses
3. **Set appropriate thresholds**: Adjust `confidence_threshold` based on your handoff capacity
4. **Use behavioral restrictions**: Clearly define topics the agent should avoid
5. **Enable features gradually**: Start with basic features, enable rich messages and suggestions once comfortable

### Knowledge Base

1. **Organize with categories**: Use consistent category names for easy filtering
2. **Use descriptive titles**: Make titles clear and searchable
3. **Add relevant keywords**: Include synonyms and common misspellings
4. **Set priorities**: Higher priority (80-100) for critical information
5. **Keep content current**: Regularly review and update entries
6. **Use semantic search**: Test search queries to ensure relevant results
7. **Bulk import for initial setup**: Use CSV import for large initial knowledge bases

### Analytics

1. **Monitor regularly**: Check analytics weekly to identify trends
2. **Track handoff reasons**: Use handoff analytics to improve knowledge base
3. **Optimize costs**: Monitor cost analytics and adjust model usage
4. **Review common topics**: Use topic analytics to add missing knowledge entries
5. **Set date ranges**: Use appropriate date ranges for meaningful insights

### Performance

1. **Cache configuration**: Agent configuration is cached for 5 minutes
2. **Paginate large results**: Use pagination for knowledge base and interactions
3. **Filter queries**: Use filters to reduce response size
4. **Batch operations**: Use bulk import for multiple knowledge entries

---

## Integration Examples

### Python Example

```python
import requests

BASE_URL = "https://api.tulia.ai/v1/bot"
HEADERS = {
    "X-TENANT-ID": "your-tenant-id",
    "X-TENANT-API-KEY": "your-api-key",
    "Content-Type": "application/json"
}

# Get agent configuration
response = requests.get(f"{BASE_URL}/agent-config", headers=HEADERS)
config = response.json()
print(f"Agent name: {config['agent_name']}")

# Create knowledge entry
entry_data = {
    "entry_type": "faq",
    "title": "What are your business hours?",
    "content": "We are open Monday-Friday 9am-5pm EST.",
    "keywords_list": ["hours", "schedule", "open"],
    "priority": 80
}
response = requests.post(f"{BASE_URL}/knowledge", headers=HEADERS, json=entry_data)
entry = response.json()
print(f"Created entry: {entry['id']}")

# Search knowledge base
params = {"q": "business hours", "limit": 5}
response = requests.get(f"{BASE_URL}/knowledge/search", headers=HEADERS, params=params)
results = response.json()
print(f"Found {len(results)} results")

# Get analytics
params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
response = requests.get(f"{BASE_URL}/analytics/conversations", headers=HEADERS, params=params)
stats = response.json()
print(f"Total interactions: {stats['total_interactions']}")
```

### JavaScript Example

```javascript
const BASE_URL = 'https://api.tulia.ai/v1/bot';
const HEADERS = {
  'X-TENANT-ID': 'your-tenant-id',
  'X-TENANT-API-KEY': 'your-api-key',
  'Content-Type': 'application/json'
};

// Get agent configuration
async function getAgentConfig() {
  const response = await fetch(`${BASE_URL}/agent-config`, { headers: HEADERS });
  const config = await response.json();
  console.log(`Agent name: ${config.agent_name}`);
  return config;
}

// Create knowledge entry
async function createKnowledgeEntry() {
  const entryData = {
    entry_type: 'faq',
    title: 'What are your business hours?',
    content: 'We are open Monday-Friday 9am-5pm EST.',
    keywords_list: ['hours', 'schedule', 'open'],
    priority: 80
  };
  
  const response = await fetch(`${BASE_URL}/knowledge`, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify(entryData)
  });
  
  const entry = await response.json();
  console.log(`Created entry: ${entry.id}`);
  return entry;
}

// Search knowledge base
async function searchKnowledge(query) {
  const params = new URLSearchParams({ q: query, limit: 5 });
  const response = await fetch(`${BASE_URL}/knowledge/search?${params}`, { headers: HEADERS });
  const results = await response.json();
  console.log(`Found ${results.length} results`);
  return results;
}

// Get analytics
async function getAnalytics() {
  const params = new URLSearchParams({
    start_date: '2024-01-01',
    end_date: '2024-01-31'
  });
  
  const response = await fetch(`${BASE_URL}/analytics/conversations?${params}`, { headers: HEADERS });
  const stats = await response.json();
  console.log(`Total interactions: ${stats.total_interactions}`);
  return stats;
}
```

---

## Support

For additional support:

- **Documentation**: https://docs.tulia.ai
- **API Status**: https://status.tulia.ai
- **Support Email**: support@tulia.ai

---

## Changelog

### Version 1.0.0 (2024-01-01)

- Initial release of AI Agent API
- Agent configuration endpoints
- Knowledge base management
- Agent interaction tracking
- Analytics endpoints
- Semantic search
- Bulk import functionality
