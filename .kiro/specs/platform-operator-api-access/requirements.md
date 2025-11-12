# Requirements Document

## Introduction

This feature enables platform operators (super admins) to access and manage the WabotIQ platform through APIs without being tied to specific tenants. Platform operators need the ability to perform cross-tenant operations, system-wide analytics, tenant management, and platform configuration through JWT-based authentication with platform-level privileges.

**Authentication Model**:
- Platform operators authenticate using JWT tokens (Authorization: Bearer header)
- Platform APIs require only JWT authentication (no tenant context)
- Tenant APIs require JWT + X-TENANT-ID + X-TENANT-API-KEY headers
- Platform operator status is determined by `user.is_superuser` flag

## Glossary

- **Platform Operator**: A super admin user (is_superuser=True) who manages the WabotIQ platform itself, not tied to any specific tenant
- **JWT Token**: JSON Web Token used for user authentication across all APIs
- **Tenant API Key**: The existing API key system that grants access to a specific tenant's resources (used alongside JWT)
- **Platform Privilege**: A permission scope that applies to platform-level operations (e.g., `platform:tenants:manage`, `platform:analytics:view`)
- **TenantContextMiddleware**: The Django middleware that validates authentication and establishes tenant context
- **Cross-Tenant Operation**: An operation that accesses or modifies data across multiple tenants
- **System**: The WabotIQ platform
- **Superuser**: A user with `is_superuser=True` flag who has platform operator privileges

## Requirements

### Requirement 1: JWT Authentication System

**User Story:** As a platform user, I want to authenticate using JWT tokens, so that I can securely access both platform and tenant APIs with a single authentication mechanism.

#### Acceptance Criteria

1. THE System SHALL provide JWT-based authentication using djangorestframework-simplejwt library
2. THE System SHALL provide endpoint `POST /v1/auth/login` that accepts email and password and returns access and refresh tokens
3. THE System SHALL provide endpoint `POST /v1/auth/refresh` that accepts refresh token and returns new access token
4. THE System SHALL include user_id, email, and is_superuser claims in JWT access tokens
5. THE System SHALL set access token expiration to 1 hour and refresh token expiration to 7 days

### Requirement 2: Platform Privilege System

**User Story:** As a platform administrator, I want to define granular privileges for platform operators, so that I can control what system-wide operations each operator can perform.

#### Acceptance Criteria

1. THE System SHALL support the following platform privilege scopes: `platform:tenants:view`, `platform:tenants:manage`, `platform:analytics:view`, `platform:users:view`, `platform:system:configure`, `platform:integrations:view`, `platform:finance:view`
2. THE System SHALL validate that platform API keys contain only recognized platform privilege scopes
3. THE System SHALL provide a service method to check if a platform API key has a specific privilege
4. THE System SHALL treat platform privileges as distinct from tenant-level RBAC scopes
5. THE System SHALL allow platform API keys to have multiple privileges simultaneously

### Requirement 3: Middleware Authentication Enhancement

**User Story:** As a platform operator, I want to authenticate API requests using my JWT token, so that I can access platform-level endpoints without requiring a tenant context.

#### Acceptance Criteria

1. WHEN a request includes valid JWT token and user.is_superuser is True, THE TenantContextMiddleware SHALL set `request.is_platform_operator` to True
2. WHEN a platform operator accesses platform endpoints, THE TenantContextMiddleware SHALL set `request.platform_privileges` based on user's superuser status
3. WHEN a request includes JWT token but user.is_superuser is False and no tenant headers present, THE TenantContextMiddleware SHALL return HTTP 403 with error message "Tenant context required"
4. WHEN a request includes JWT token plus X-TENANT-ID and X-TENANT-API-KEY headers, THE TenantContextMiddleware SHALL validate tenant context and resolve RBAC scopes
5. WHEN JWT authentication fails, THE TenantContextMiddleware SHALL return HTTP 401 with error message "Invalid or expired token"

### Requirement 4: Platform Permission Class

**User Story:** As a developer, I want a DRF permission class for platform endpoints, so that I can easily protect platform-level APIs with privilege checks.

#### Acceptance Criteria

1. THE System SHALL provide a `HasPlatformPrivileges` DRF permission class
2. WHEN a view uses `HasPlatformPrivileges`, THE System SHALL check that `request.is_platform_operator` is true
3. WHEN a view defines `required_platform_privileges` attribute, THE System SHALL verify the platform API key has all required privileges
4. WHEN a platform operator lacks required privileges, THE System SHALL return HTTP 403 with error message listing missing privileges
5. THE System SHALL provide a `@requires_platform_privileges` decorator for class-based views

### Requirement 5: Platform Tenant Management API

**User Story:** As a platform operator, I want to view and manage all tenants through an API, so that I can perform administrative tasks without accessing individual tenant contexts.

#### Acceptance Criteria

1. THE System SHALL provide endpoint `GET /v1/platform/tenants` that returns paginated list of all tenants with required privilege `platform:tenants:view`
2. THE System SHALL provide endpoint `GET /v1/platform/tenants/{id}` that returns detailed tenant information with required privilege `platform:tenants:view`
3. THE System SHALL provide endpoint `POST /v1/platform/tenants` that creates a new tenant with required privilege `platform:tenants:manage`
4. THE System SHALL provide endpoint `PATCH /v1/platform/tenants/{id}` that updates tenant details with required privilege `platform:tenants:manage`
5. THE System SHALL provide endpoint `POST /v1/platform/tenants/{id}/suspend` that suspends a tenant with required privilege `platform:tenants:manage`

### Requirement 6: Platform Analytics API

**User Story:** As a platform operator, I want to view system-wide analytics across all tenants, so that I can monitor platform health and usage patterns.

#### Acceptance Criteria

1. THE System SHALL provide endpoint `GET /v1/platform/analytics/overview` that returns aggregated metrics across all tenants with required privilege `platform:analytics:view`
2. THE System SHALL include metrics for total tenants, active tenants, total customers, total orders, total messages, and total revenue
3. THE System SHALL provide endpoint `GET /v1/platform/analytics/tenants` that returns per-tenant metrics with required privilege `platform:analytics:view`
4. THE System SHALL support date range filtering via query parameters `start_date` and `end_date`
5. THE System SHALL calculate metrics efficiently using database aggregation queries

### Requirement 7: Audit Logging for Platform Operations

**User Story:** As a platform administrator, I want all platform operator actions to be logged, so that I can audit system-wide changes and maintain security compliance.

#### Acceptance Criteria

1. WHEN a platform operator performs any create, update, or delete operation, THE System SHALL create an audit log entry
2. THE System SHALL store audit logs with fields for timestamp, platform API key identifier, action type, resource type, resource ID, and change details
3. THE System SHALL provide endpoint `GET /v1/platform/audit-logs` that returns paginated audit logs with required privilege `platform:system:configure`
4. THE System SHALL support filtering audit logs by date range, action type, and resource type
5. THE System SHALL retain audit logs for minimum 90 days

### Requirement 8: Backward Compatibility

**User Story:** As a system maintainer, I want the platform operator feature to work alongside existing tenant-based authentication, so that current tenant APIs continue to function without modification.

#### Acceptance Criteria

1. WHEN a request uses `X-TENANT-API-KEY` header without `X-PLATFORM-API-KEY`, THE System SHALL authenticate using existing tenant-based flow
2. THE System SHALL maintain all existing tenant-scoped RBAC functionality unchanged
3. THE System SHALL ensure tenant-scoped endpoints reject platform API key authentication
4. THE System SHALL ensure platform-scoped endpoints reject tenant API key authentication
5. THE System SHALL maintain backward compatibility with all existing API clients

### Requirement 9: Security Controls

**User Story:** As a security administrator, I want platform API keys to have security controls, so that I can prevent unauthorized access and detect suspicious activity.

#### Acceptance Criteria

1. THE System SHALL rate-limit platform API endpoints to maximum 100 requests per minute per API key
2. WHEN a platform API key is used from a new IP address, THE System SHALL log the event for security monitoring
3. THE System SHALL provide endpoint `POST /v1/platform/api-keys/{id}/rotate` that generates a new key value while maintaining privileges
4. THE System SHALL support setting expiration dates on platform API keys
5. WHEN a platform API key expires, THE System SHALL automatically deactivate it and reject authentication attempts

### Requirement 10: Documentation and Developer Experience

**User Story:** As a platform operator, I want clear documentation on using platform API keys, so that I can quickly understand how to authenticate and what operations I can perform.

#### Acceptance Criteria

1. THE System SHALL include platform endpoints in OpenAPI schema with security scheme for platform API keys
2. THE System SHALL document all platform privilege scopes in API documentation
3. THE System SHALL provide example curl commands for each platform endpoint in docstrings
4. THE System SHALL return descriptive error messages when platform authentication fails
5. THE System SHALL include platform API key usage in the main README or deployment documentation
