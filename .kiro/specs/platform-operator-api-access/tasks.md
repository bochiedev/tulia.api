# Implementation Plan

- [ ] 1. Install and configure JWT authentication
  - Install `djangorestframework-simplejwt` package via pip
  - Add JWT authentication to REST_FRAMEWORK settings in `config/settings.py`
  - Configure JWT token expiration (access: 1 hour, refresh: 7 days)
  - Add JWT_AUTH settings for token signing and validation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 2. Create authentication endpoints
  - Create `apps/core/views_auth.py` with RegisterView, LoginView, RefreshTokenView, LogoutView
  - Implement user registration with email verification
  - Implement login endpoint that returns JWT access and refresh tokens
  - Implement token refresh endpoint
  - Create serializers for registration, login, and token responses
  - Add authentication URLs to `apps/core/urls.py` under `/v1/auth/` prefix
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 3. Implement platform privilege system
  - Define `PLATFORM_PRIVILEGES` constant dictionary in `apps/rbac/constants.py` with all canonical platform privilege codes and descriptions
  - Create `PlatformPrivilegeService` class in `apps/rbac/services.py` with methods for privilege validation and checking
  - Implement `get_platform_privileges(user)` method that returns privileges based on is_superuser flag
  - Implement `has_platform_privilege(user, privilege)` method to check if user has specific platform privilege
  - Implement `get_all_platform_privileges()` method to return complete privilege dictionary
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 4. Enhance TenantContextMiddleware for JWT and platform authentication
  - Modify `process_request()` to check for JWT authentication first (request.user set by DRF)
  - Add `_check_platform_operator()` method to detect superuser and set platform context
  - When user.is_superuser=True and no tenant headers, set `request.is_platform_operator=True`
  - Set `request.platform_privileges` based on superuser status
  - When JWT present but not superuser and no tenant headers, return 403 "Tenant context required"
  - Keep existing tenant authentication logic for JWT + tenant headers combination
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 5. Create platform permission class and decorator
  - Implement `HasPlatformPrivileges` permission class in `apps/core/permissions.py`
  - Add `has_permission()` method to check `request.is_platform_operator` and verify required privileges
  - Implement logging for permission denials with missing privileges
  - Create `@requires_platform_privileges()` decorator for declaring required privileges on views
  - Add support for both class-level and method-level privilege requirements
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 6. Create platform tenant management API endpoints
  - Create `apps/platform/` app with models.py, views.py, serializers.py, urls.py structure
  - Implement `GET /v1/platform/tenants` endpoint with pagination, filtering, and search (requires JWT + is_superuser)
  - Implement `GET /v1/platform/tenants/{id}` endpoint for detailed tenant information
  - Implement `POST /v1/platform/tenants` endpoint for tenant creation
  - Implement `PATCH /v1/platform/tenants/{id}` endpoint for tenant updates
  - Implement `POST /v1/platform/tenants/{id}/suspend` endpoint for tenant suspension
  - Implement `POST /v1/platform/tenants/{id}/activate` endpoint for tenant activation
  - Add appropriate serializers for tenant data with validation
  - Wire up URL routing in main `config/urls.py`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 7. Create platform analytics API endpoints
  - Implement `GET /v1/platform/analytics/overview` endpoint with aggregated metrics across all tenants
  - Implement `GET /v1/platform/analytics/tenants` endpoint with per-tenant metrics and pagination
  - Implement `GET /v1/platform/analytics/growth` endpoint with time-series growth data
  - Add date range filtering support via `start_date` and `end_date` query parameters
  - Use database aggregation queries for efficient metric calculation
  - Implement caching for analytics results with 10-minute TTL
  - Create serializers for analytics response data
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 8. Create platform audit log API endpoints
  - Implement `GET /v1/platform/audit-logs` endpoint with pagination and filtering
  - Implement `GET /v1/platform/audit-logs/{id}` endpoint for detailed audit log entry
  - Add filtering support for date range, action type, tenant_id, and user_email
  - Create serializers for audit log data
  - Extend `AuditLog.log_action()` with `log_platform_action()` class method for platform operations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 9. Implement security controls
  - Add rate limiting to platform endpoints using `django-ratelimit` decorator (100/min for reads, 20/min for writes)
  - Implement IP address tracking and logging for platform operator actions
  - Add JWT token blacklisting for logout functionality
  - Add security logging for failed authentication attempts
  - Implement brute force protection on login endpoint (10 attempts per IP per hour)
  - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [ ] 10. Add Django admin interfaces for superuser management
  - Update User model admin to show is_superuser flag prominently
  - Add admin action to promote/demote users to/from superuser status
  - Add audit logging when superuser status changes
  - Create admin view to show platform operator activity logs
  - _Requirements: 1.4_

- [ ] 11. Create management command for creating superuser with platform access
  - Implement `create_platform_operator` management command in `apps/rbac/management/commands/`
  - Add command arguments: `--email`, `--password`, `--first-name`, `--last-name`
  - Set is_superuser=True on created user
  - Display confirmation message with user details
  - Include usage examples in command help text
  - _Requirements: 1.1, 1.2_

- [ ] 12. Update OpenAPI schema documentation
  - Add JWT Bearer authentication security scheme to OpenAPI configuration
  - Document all platform endpoints with request/response schemas
  - Add `x-required-privileges` extension to platform endpoints
  - Include error response schemas (401, 403, 429)
  - Add example requests with curl commands showing JWT usage in endpoint docstrings
  - Document authentication endpoints (register, login, refresh)
  - Generate updated schema.yml file
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 13. Write comprehensive tests
- [ ] 13.1 Write unit tests for JWT authentication
  - Test user registration, login, token generation, token validation, token refresh
  - Test token expiration handling
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 13.2 Write unit tests for PlatformPrivilegeService
  - Test privilege resolution for superusers, has_privilege checking, and get_all_privileges
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 13.3 Write middleware tests for JWT and platform authentication
  - Test JWT validation, superuser detection, platform operator context setting
  - Test tenant context with JWT + tenant headers
  - Test rejection when JWT missing or invalid
  - Test public path bypass
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 13.4 Write permission class tests
  - Test HasPlatformPrivileges with superuser/non-superuser
  - Test decorator functionality
  - Test tenant user rejection on platform endpoints
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 13.5 Write API integration tests for authentication endpoints
  - Test registration flow with email verification
  - Test login with valid/invalid credentials
  - Test token refresh
  - Test logout and token blacklisting
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 13.6 Write API integration tests for tenant management endpoints
  - Test list, get, create, update, suspend, activate operations with superuser JWT
  - Test rejection when non-superuser attempts platform operations
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 13.7 Write API integration tests for analytics endpoints
  - Test overview, per-tenant, and growth endpoints with superuser JWT
  - Test date filtering and privilege checks
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 13.8 Write API integration tests for audit log endpoints
  - Test list and detail endpoints with filtering and privilege checks
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 13.9 Write security tests
  - Test rate limiting on auth and platform endpoints
  - Test brute force protection
  - Test JWT token expiration and refresh
  - Test cross-tenant access isolation
  - Test endpoint isolation (platform vs tenant)
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 13.10 Write backward compatibility tests
  - Test that existing tenant APIs work with JWT + tenant headers
  - Test no breaking changes to tenant authentication flow
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 14. Create deployment documentation
  - Document JWT configuration and secret key management
  - Write initial setup guide for creating first superuser
  - Document authentication flow for platform operators vs tenant users
  - Add example usage with curl commands showing JWT authentication
  - Include security best practices for JWT token management
  - Update main README with authentication architecture section
  - Reference AUTHENTICATION_ARCHITECTURE.md for complete details
  - _Requirements: 10.5_
