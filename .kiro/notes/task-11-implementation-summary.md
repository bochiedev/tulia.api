# Task 11 Implementation Summary: Messaging Service with Consent and Rate Limiting

## Overview
Successfully implemented a comprehensive messaging service for the Tulia AI WhatsApp platform with consent validation, rate limiting, template support, and message scheduling capabilities.

## Completed Subtasks

### 11.1 Create MessageTemplate and ScheduledMessage models ✅
**Files Modified:**
- `apps/messaging/models.py` - Added `ScheduledMessage` model
- `apps/messaging/migrations/0003_add_scheduled_message.py` - Created migration

**Implementation Details:**
- `MessageTemplate` model already existed with placeholder support and usage tracking
- Added `ScheduledMessage` model with:
  - Support for individual and broadcast messages
  - Status tracking (pending, sent, failed, canceled)
  - Template integration with context data
  - Recipient criteria for campaign targeting
  - Metadata for campaign/appointment references
  - Delivery tracking with timestamps and error messages

### 11.2 Implement MessagingService for outbound messages ✅
**Files Created:**
- `apps/messaging/services/messaging_service.py` - Core messaging service

**Files Modified:**
- `apps/messaging/services/__init__.py` - Exported new service classes
- `apps/integrations/services/__init__.py` - Exported `create_twilio_service_for_tenant`

**Implementation Details:**
- **send_message()**: Main method for sending outbound messages with:
  - Consent validation (can be skipped for transactional messages)
  - Rate limit checking (can be skipped for critical messages)
  - Template application with placeholder replacement
  - Twilio integration for actual message delivery
  - Message record creation with delivery tracking
  - Rate limit counter increment
  - Warning threshold checking

- **check_rate_limit()**: Redis-based sliding window rate limiting
  - Uses Redis sorted sets with timestamps as scores
  - Automatically removes old entries (>24 hours)
  - Returns true/false based on tier limits
  - Handles unlimited tiers gracefully

- **apply_template()**: Template rendering with {{placeholder}} syntax
  - Regex-based placeholder detection
  - Context-based replacement
  - Automatic usage count increment

- **schedule_message()**: Schedule messages for future delivery
  - Validates scheduled_at is in future
  - Adjusts for quiet hours if applicable
  - Creates ScheduledMessage record
  - Supports both individual and broadcast messages

- **respect_quiet_hours()**: Timezone-aware quiet hours enforcement
  - Uses customer timezone or falls back to tenant timezone
  - Handles quiet hours spanning midnight
  - Overrides for time-sensitive messages (transactional, reminders)
  - Delays messages to end of quiet hours

- **get_rate_limit_status()**: Returns current rate limit status
  - Current count, daily limit, percentage used
  - Remaining messages
  - Warning threshold status

- **queue_excess_messages()**: Queues messages exceeding daily limit
  - Schedules for next day at 8 AM tenant time
  - Marks with metadata flag

**Custom Exceptions:**
- `MessagingServiceError` - Base exception
- `RateLimitExceeded` - Rate limit exceeded
- `ConsentRequired` - Customer consent required but not granted

### 11.3 Implement rate limiting with warnings ✅
**Implementation Details:**
Integrated into MessagingService:
- **Redis sliding window**: 24-hour rolling window using sorted sets
- **Warning at 80%**: Automatic warning when 80% of daily limit reached
- **One warning per day**: Cache flag prevents duplicate warnings
- **Excess message queueing**: Messages exceeding limit queued for next day
- **Account flagging**: Logged for review and tier upgrade recommendations

**Rate Limit Features:**
- Per-tenant tracking using Redis
- Automatic cleanup of old entries
- Tier-based limits (Starter: 1000/day, Growth: 10000/day, Enterprise: unlimited)
- Fail-open on Redis errors (allows messages)
- Warning notifications logged (TODO: email/SMS integration)

### 11.4 Create messaging REST API endpoints ✅
**Files Modified:**
- `apps/messaging/serializers.py` - Added 8 new serializers
- `apps/messaging/views.py` - Added 4 new view classes
- `apps/messaging/urls.py` - Added 4 new URL patterns

**New Serializers:**
1. `SendMessageSerializer` - For sending outbound messages
2. `ScheduleMessageSerializer` - For scheduling messages
3. `MessageTemplateSerializer` - For template CRUD
4. `MessageTemplateCreateSerializer` - For template creation
5. `ScheduledMessageSerializer` - For scheduled message details
6. `RateLimitStatusSerializer` - For rate limit status

**New API Endpoints:**

1. **POST /v1/messages/send**
   - Send outbound message with consent and rate limit checks
   - Required scope: `conversations:view`
   - Request: customer_id, content, message_type, optional template
   - Response: message_id, status, provider_msg_id
   - Error codes: 400 (invalid), 403 (consent), 404 (not found), 429 (rate limit), 500 (error)

2. **POST /v1/messages/schedule**
   - Schedule message for future delivery
   - Required scope: `conversations:view`
   - Request: customer_id (optional for broadcast), content, scheduled_at, message_type
   - Response: ScheduledMessage details
   - Validates scheduled_at is in future
   - Adjusts for quiet hours automatically

3. **GET /v1/templates**
   - List message templates for tenant
   - Required scope: `conversations:view`
   - Query params: message_type (filter)
   - Response: Array of MessageTemplate objects

4. **POST /v1/templates**
   - Create new message template
   - Required scope: `conversations:view`
   - Request: name, content, message_type, description, variables
   - Validates placeholder syntax
   - Response: Created MessageTemplate

5. **GET /v1/messages/rate-limit-status**
   - Get current rate limit status
   - Required scope: `analytics:view`
   - Response: current_count, daily_limit, percentage_used, remaining, warning_threshold_reached

**OpenAPI Documentation:**
- All endpoints documented with drf-spectacular
- Request/response schemas defined
- Error responses documented
- Query parameters documented
- Tagged under 'Messaging'

## Key Features Implemented

### Consent Management Integration
- Automatic consent checking before sending messages
- Support for skipping consent for transactional messages
- Integration with ConsentService
- Proper error handling with ConsentRequired exception

### Rate Limiting
- Redis-based sliding window algorithm
- Per-tenant tracking with 24-hour window
- Tier-based limits from SubscriptionTier model
- Warning at 80% threshold
- Excess message queueing for next day
- Rate limit status API endpoint

### Template System
- {{placeholder}} syntax support
- Regex-based placeholder detection and replacement
- Usage count tracking
- Template validation on creation
- Template context support for dynamic content

### Message Scheduling
- Future delivery scheduling
- Quiet hours enforcement with timezone handling
- Support for individual and broadcast messages
- Recipient criteria for campaign targeting
- Status tracking (pending, sent, failed, canceled)

### Quiet Hours
- Timezone-aware enforcement
- Customer timezone or tenant timezone fallback
- Handles quiet hours spanning midnight
- Override for time-sensitive messages
- Automatic adjustment of scheduled times

### Error Handling
- Custom exceptions for different error types
- Proper HTTP status codes
- Detailed error messages
- Logging with structured context
- Graceful degradation on Redis errors

## Testing Recommendations

### Unit Tests
- [ ] Test send_message with consent validation
- [ ] Test send_message with rate limiting
- [ ] Test apply_template with various placeholders
- [ ] Test schedule_message validation
- [ ] Test respect_quiet_hours with different timezones
- [ ] Test rate limit counter increment/decrement
- [ ] Test warning threshold detection

### Integration Tests
- [ ] Test full message sending flow with Twilio
- [ ] Test scheduled message execution
- [ ] Test rate limit enforcement across multiple messages
- [ ] Test quiet hours adjustment
- [ ] Test template rendering with real data
- [ ] Test consent blocking
- [ ] Test rate limit warning notifications

### API Tests
- [ ] Test POST /v1/messages/send with valid data
- [ ] Test POST /v1/messages/send without consent (403)
- [ ] Test POST /v1/messages/send exceeding rate limit (429)
- [ ] Test POST /v1/messages/schedule with future date
- [ ] Test POST /v1/messages/schedule with past date (400)
- [ ] Test GET /v1/templates filtering
- [ ] Test POST /v1/templates with invalid placeholders (400)
- [ ] Test GET /v1/messages/rate-limit-status

## Dependencies
- Django REST Framework
- drf-spectacular (OpenAPI)
- Redis (for rate limiting)
- Twilio SDK (for message delivery)
- pytz (for timezone handling)

## Configuration Requirements
- Redis must be configured and accessible
- Twilio credentials must be set per tenant
- SubscriptionTier limits must be configured
- Quiet hours must be configured per tenant

## Next Steps
Task 12 will implement automated messaging system with Celery tasks for:
- Transactional messages (payment confirmations, shipment notifications)
- Appointment reminders (24h and 2h before)
- Re-engagement messages for inactive conversations
- Integration with order and appointment workflows

## Notes
- All code follows Django and DRF best practices
- Proper tenant scoping enforced throughout
- RBAC integration with required_scopes
- Comprehensive logging for debugging and monitoring
- OpenAPI documentation for all endpoints
- Error handling with appropriate HTTP status codes
