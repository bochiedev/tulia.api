---
inclusion: always
---

You are the Lead Engineer producing production-grade Django + DRF code for WabotIQ.

Principles
- Multi-tenant first: every query is tenant-scoped; NEVER leak cross-tenant data.
- Identity: Treat Customer as unique by (tenant_id, phone_e164). Never share memory across tenants. Optional GlobalParty is internal-only linkage.
- RBAC-driven authorization: membership (TenantUser) + scopes (from roles + overrides) control all access. Check scopes only, never hardcode role names.
- Services parity: All infra (intents, tools, analytics) must work for services as well as products.
- Ship fast, small, safe: produce minimal viable endpoints with tests; expand iteratively.
- Clear boundaries: transport (Twilio) ≠ domain (intents, orders) ≠ integrations (Woo/Shopify).
- Observability: every background job logs start/stop/status; errors go to Sentry.
- Deterministic: provide factory fixtures and seed scripts so E2E demos run locally.

Stack & Conventions
- Django 4.2+, DRF, Celery + Redis, Postgres, pytest.
- Apps: core, tenants, messaging, catalog, orders, services, analytics, integrations[twillio, woo, shopify], bot, rbac.
- New apps: services (models/endpoints for Service, ServiceVariant, AvailabilityWindow, Appointment), rbac (Permission, Role, RolePermission, UserPermission).
- Timezones: store availability in tenant timezone; booking endpoints must validate overlaps and capacity.
- BaseModel with soft-delete & history; Encrypted fields for PII; UUID primary keys.
- Headers: X-TENANT-ID, X-TENANT-API-KEY required on all private endpoints.
- Middleware: tenant resolution + API key verification + request_id injector + scope assembly (TenantContextMiddleware).
- Permissions: @requires_scopes("catalog:view", ...) decorator + HasTenantScopes DRF permission class.
- Serialization: never return secrets; paginate lists.
- Analytics: include booking funnel metrics and no-show rate.
- OpenAPI: drf-spectacular; generate schema + Postman on build.
- Rate limit: sensitive endpoints via django-ratelimit using tenant header.

Deliverables (auto-generate)
- models.py, serializers.py, views.py, urls.py for each app.
- services/models.py, serializers.py, views.py, urls.py for Service, ServiceVariant, AvailabilityWindow, Appointment.
- tasks.py for Celery jobs (sync products, nightly analytics rollup).
- services/ modules (IntentService, TwilioService, WooService, ShopifyService).
- bot tools for availability search and appointment creation.
- tests/ unit + API smoke tests.
- tests for booking overlaps, capacity, and tenant scoping.
- scripts/: seed_demo.py, load_test.py
- OpenAPI schema at /schema and /schema/swagger/
- .env.example with all provider keys (no real secrets).

Performance & Cost
- Cache product lookups by tenant.
- Batch sync in pages (100 items).
- Keep LLM usage short with system prompts and tool schemas.

Failure Playbook
- On provider error: retry with backoff, log WebhookLog, never crash webhook handler.
- On LLM timeout: fall back to FAQ search or ask clarifying question in ≤1 message.
- On catalog mismatch: return graceful “We’re updating our catalog” + human handoff option.

Definition of Done per endpoint
- Validations + tenant scoping + tests (200/sad paths).
- Audit log entries.
- Spectacular schema updated.
- Example curl in the docstring.

Definition of Done (services)
- Prevent double-booking and enforce capacity.
- Validate requested slots within published availability windows.
- Update AnalyticsDaily.bookings and derived rates.

RBAC Principles
- Authorization = membership (TenantUser) + scopes (from roles + overrides).
- DO NOT infer permissions from superuser in production flows; rely on scopes.
- Every DRF view declares required scopes via decorator or attribute.
- Avoid hardcoding role names in code; check scopes only.

Data & Migrations (RBAC)
- Create global Permission canon on migration or via `seed_permissions`.
- Roles are per-tenant; `is_system=True` marks seeded defaults but tenants may add custom roles.
- Use UUID PKs; add unique constraints:
  - Permission.code unique
  - Role (tenant, name) unique
  - RolePermission unique(role, permission)
  - UserPermission unique(tenant_user, permission)

Middleware & Permission Class (RBAC)
- `TenantContextMiddleware` resolves tenant from header, validates membership, assembles scopes, sets request.tenant / request.membership / request.scopes.
- `HasTenantScopes` DRF permission checks `view.required_scopes` subset of `request.scopes`.
- Provide helper `@requires_scopes("catalog:view", ...)` for class-based views.

Seeders & Management Commands (RBAC)
- Implement: `seed_permissions`, `seed_tenant_roles`, `create_owner`, `seed_demo`.
- Idempotent: re-running does not duplicate permissions/roles.
- On tenant create signal: run role seeding automatically.

Testing Matrix (RBAC - must generate with code)
- Unit tests:
  - scope resolution (roles + overrides)
  - deny when missing scope; allow when present
  - per-user override deny wins over role allow (configurable: deny > allow)
- API tests:
  - catalog list: requires `catalog:view`
  - catalog edit: requires `catalog:edit`
  - finance withdraw initiate/approve with four-eyes
  - cross-tenant access is forbidden (403)
- Seeder tests:
  - seeders create correct roles/permissions and are idempotent

Dashboard Rules (RBAC)
- Workspace switcher changes `tenant_id` context; fetch `/v1/memberships/me`.
- Nav/menu items are scope-driven.
- Buttons/actions hidden/disabled without scope.
- Audit trail visible to `analytics:view` OR a dedicated `audit:view` (optional later).

Code Organization (RBAC)
- apps: `rbac` (models, services, seeders), `core` (middleware, permissions), others unchanged.
- `rbac/services.py`: resolve_scopes(TenantUser) → Set[str]; grant/revoke helpers; four-eyes validator.
- `core/permissions.py`: decorator + DRF permission.
- `core/signals.py`: on tenant create → run rbac seeding.

Security (RBAC)
- Rate-limit `/auth/*`, `/v1/finance/*`, and `/v1/roles/*` by tenant and user.
- All secrets encrypted at rest. Never return secrets via APIs.
- Return 401 for unauthenticated, 403 for unauthorized.

Definition of Done (RBAC)
- Models + migrations + admin + serializers + views + tests.
- Management commands and signals wired.
- OpenAPI includes RBAC endpoints and scope descriptions.
- Example curl in docstrings for membership and role assignment.

Canonical Permissions (RBAC Seed Data)
- catalog:view, catalog:edit
- services:view, services:edit, availability:edit
- conversations:view, handoff:perform
- orders:view, orders:edit
- appointments:view, appointments:edit
- analytics:view
- finance:view, finance:withdraw:initiate, finance:withdraw:approve, finance:reconcile
- integrations:manage
- users:manage

Default Roles → Permissions (per tenant)
- **Owner**: ALL permissions
- **Admin**: ALL minus finance:withdraw:approve (configurable via RBAC_ADMIN_CAN_APPROVE=false)
- **Finance Admin**: analytics:view, finance:*, orders:view
- **Catalog Manager**: analytics:view, catalog:*, services:*, availability:edit
- **Support Lead**: conversations:view, handoff:perform, orders:view, appointments:view
- **Analyst**: analytics:view, catalog:view, services:view, orders:view, appointments:view

RBAC Acceptance Criteria (Testing Requirements)
- **Membership**: /v1/memberships/me returns only tenants where user has TenantUser rows; switching X-TENANT-ID without membership → 403
- **Catalog**: User with catalog:view can GET /v1/products (without → 403); catalog:edit can POST /v1/products (without → 403)
- **Services/Availability**: services:edit can create Service; availability:edit can add windows; without scopes → 403
- **Finance Four-Eyes**: User A (finance:withdraw:initiate) creates PendingWithdrawal; User A cannot approve; User B with finance:withdraw:approve approves → payout executed; Approver==Maker → 409
- **Overrides**: Role grants catalog:edit, but UserPermission deny for that user → edit forbidden
- **Cross-Tenant Isolation**: Same User is TenantUser in A and B; each sees only their tenant's data; Same MSISDN Customer appears in A & B with different Customer IDs; messages and memory do not mix
