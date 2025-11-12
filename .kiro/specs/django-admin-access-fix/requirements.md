# Requirements Document

## Introduction

The Django admin interface at `/admin` is currently blocked by the tenant authentication middleware, which requires `X-TENANT-ID` and `X-TENANT-API-KEY` headers. The admin should be accessible to Django superusers without these headers, as it uses Django's built-in session-based authentication.

## Glossary

- **TenantContextMiddleware**: Middleware that validates tenant context from request headers for API endpoints
- **Django Admin**: Django's built-in administrative interface at `/admin`
- **Public Path**: URL path that bypasses tenant authentication requirements
- **Session Authentication**: Django's built-in authentication using session cookies

## Requirements

### Requirement 1

**User Story:** As a Django superuser, I want to access the Django admin interface at `/admin` without providing tenant headers, so that I can manage the system using standard Django authentication.

#### Acceptance Criteria

1. WHEN a user navigates to `/admin`, THE TenantContextMiddleware SHALL skip tenant header validation
2. WHEN a user navigates to any path starting with `/admin/`, THE TenantContextMiddleware SHALL skip tenant header validation
3. WHEN tenant header validation is skipped, THE TenantContextMiddleware SHALL set request.tenant to None
4. WHEN tenant header validation is skipped, THE TenantContextMiddleware SHALL set request.membership to None
5. WHEN tenant header validation is skipped, THE TenantContextMiddleware SHALL set request.scopes to an empty set

### Requirement 2

**User Story:** As a developer, I want the public paths list to be clearly documented, so that I understand which endpoints bypass tenant authentication.

#### Acceptance Criteria

1. THE TenantContextMiddleware SHALL maintain a PUBLIC_PATHS list that includes `/admin/`
2. THE PUBLIC_PATHS list SHALL include inline comments explaining why each path is public
3. THE middleware SHALL log at debug level when a request bypasses tenant authentication

### Requirement 3

**User Story:** As a system administrator, I want API endpoints to remain protected by tenant authentication, so that multi-tenant data isolation is maintained.

#### Acceptance Criteria

1. WHEN a user accesses any `/v1/` endpoint without tenant headers, THE TenantContextMiddleware SHALL return a 401 error
2. WHEN a user accesses webhook endpoints, THE TenantContextMiddleware SHALL skip tenant header validation
3. WHEN a user accesses the health check endpoint, THE TenantContextMiddleware SHALL skip tenant header validation
4. WHEN a user accesses the OpenAPI schema endpoints, THE TenantContextMiddleware SHALL skip tenant header validation
