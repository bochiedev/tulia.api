# Tulia AI - Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **[BREAKING]** Upgraded PostgreSQL driver from `psycopg2-binary` (v2.9.9) to `psycopg[binary]` (v3.2.3)
  - Provides better performance and type safety
  - Fully compatible with Django 4.2+
  - No code changes required
  - See [MIGRATION_PSYCOPG3.md](MIGRATION_PSYCOPG3.md) for details

### Updated
- Documentation updated to reference psycopg3 driver
- DEPLOYMENT.md: Added psycopg3 note to prerequisites
- README.md: Added psycopg3 note to prerequisites
- SETUP_COMPLETE.md: Added psycopg3 to PostgreSQL configuration section
- QUICKSTART.md: Added psycopg3 verification to troubleshooting

### Verified
- ✅ All existing tests pass with psycopg3
- ✅ Django check passes
- ✅ Database migrations work correctly
- ✅ Health check endpoint functional

## [0.1.0] - 2024-01-XX

### Added
- Initial Django project structure with multi-tenant architecture
- Core apps: core, tenants, messaging, catalog, orders, services, analytics, integrations, bot
- BaseModel with UUID primary keys, soft delete, and timestamps
- PostgreSQL configuration with connection pooling
- Redis cache and Celery task queue setup
- Structured JSON logging with request ID tracking
- Sentry integration for error tracking
- Health check endpoint at `/v1/health/`
- OpenAPI schema generation with drf-spectacular
- Swagger UI at `/schema/swagger/`
- Docker Compose configuration for local development
- Comprehensive documentation (README, DEPLOYMENT, QUICKSTART)
- Test suite with pytest and coverage reporting
- Setup script for automated environment configuration

### Infrastructure
- Django 4.2.11
- Django REST Framework 3.14.0
- PostgreSQL with psycopg3 driver
- Redis 5.0.1 for caching and Celery broker
- Celery 5.3.6 with separate queues (default, integrations, analytics, messaging, bot)
- Python 3.12+ support

### Security
- Environment-based configuration with django-environ
- Encrypted PII fields support (cryptography)
- CORS configuration
- Rate limiting setup (django-ratelimit)
- Custom exception handler with request ID tracking

### Development Tools
- Makefile with common commands
- pytest configuration with coverage
- Docker Compose for PostgreSQL, Redis, Web, and Celery
- Setup script for automated installation
- .env.example with all required variables

