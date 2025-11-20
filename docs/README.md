# Tulia AI Documentation

Complete documentation for the Tulia AI WhatsApp Commerce Platform.

## 📚 Quick Start

- **[Quick Start Deployment](QUICKSTART_DEPLOYMENT.md)** - Get up and running in 10 minutes
- **[Quick Start Guide](guides/QUICKSTART.md)** - Alternative quick start guide
- **[Twilio Webhook Setup](TWILIO_WEBHOOK_SETUP.md)** - Configure Twilio webhooks with ngrok

## 🚀 Deployment

- **[Deployment Guide](DEPLOYMENT.md)** - Comprehensive deployment guide
- **[Tenant Onboarding Deployment](TENANT_ONBOARDING_DEPLOYMENT.md)** - Onboarding feature deployment guide
- **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment checklist
- **[Environment Variables](ENVIRONMENT_VARIABLES.md)** - Complete environment variable reference
- **[Startup Validation](STARTUP_VALIDATION.md)** - Security validation on startup
- **[Database Migrations](DATABASE_MIGRATIONS.md)** - Migration procedures and best practices
- **[Documentation Index](DEPLOYMENT_DOCS_INDEX.md)** - Complete documentation index

## 🔄 CI/CD

- **[CI/CD Setup Guide](CI_CD_SETUP.md)** - Complete CI/CD configuration for GitHub Actions and GitLab CI
- **[CI/CD Quick Reference](CI_CD_QUICK_REFERENCE.md)** - Quick setup and troubleshooting guide

## 📊 Monitoring

- **[Monitoring Setup](MONITORING_SETUP.md)** - Complete monitoring and alerting guide
- **[Monitoring Quick Start](monitoring/MONITORING_QUICK_START.md)** - Quick monitoring setup
- **[Monitoring Implementation](monitoring/MONITORING_IMPLEMENTATION_SUMMARY.md)** - Implementation details
- **[Monitoring Guide](monitoring/MONITORING.md)** - Additional monitoring documentation

## 🤖 AI & Bot Features

- **[Conversational Commerce UX Enhancement](conversational-commerce-ux-enhancement/README.md)** - Complete documentation for UX enhancements
  - [API Documentation](conversational-commerce-ux-enhancement/API_DOCUMENTATION.md) - Technical API reference
  - [User Guide](conversational-commerce-ux-enhancement/USER_GUIDE.md) - End-user feature guide
  - [Admin Guide](conversational-commerce-ux-enhancement/ADMIN_GUIDE.md) - Configuration and management
  - [Deployment Checklist](conversational-commerce-ux-enhancement/DEPLOYMENT_CHECKLIST.md) - Deployment procedures
  - [Rollback Plan](conversational-commerce-ux-enhancement/ROLLBACK_PLAN.md) - Emergency rollback procedures

## 🔌 API Documentation

- **[API Quick Reference](api/API_QUICK_REFERENCE.md)** - Quick API reference
- **[Tenant Onboarding API Guide](api/TENANT_ONBOARDING_API_GUIDE.md)** - Complete onboarding API guide
- **[OpenAPI RBAC Guide](api/OPENAPI_RBAC_GUIDE.md)** - RBAC in OpenAPI documentation
- **[Postman Guide](api/POSTMAN_GUIDE.md)** - Using Postman collection
- **[Postman README](api/POSTMAN_README.md)** - Postman collection overview
- **[Postman Test Scenarios](api/POSTMAN_TEST_SCENARIOS.md)** - Test scenarios
- **[Postman Collection Summary](api/POSTMAN_COLLECTION_SUMMARY.md)** - Collection summary

## 📖 Guides

- **[Tenant Onboarding Guide](guides/TENANT_ONBOARDING_GUIDE.md)** - Step-by-step onboarding for tenants
- **[Demo Data Guide](guides/DEMO_DATA_GUIDE.md)** - Loading demo data
- **[Quick Start](guides/QUICKSTART.md)** - Getting started guide

## 🔒 Security

- **[Rate Limiting Guide](RATE_LIMITING.md)** - Comprehensive rate limiting documentation
- **[Redis Rate Limiting](REDIS_RATE_LIMITING.md)** - Redis configuration for rate limiting
- **[Security Best Practices](SECURITY_BEST_PRACTICES.md)** - Security guidelines
- **[Webhook Security](WEBHOOK_SECURITY_QUICK_REFERENCE.md)** - Webhook signature verification

## 🔧 Implementation Details

- **[RBAC Audit Report](implementation/RBAC_AUDIT_REPORT.md)** - RBAC implementation audit
- **[RBAC Fix Summary](implementation/RBAC_FIX_SUMMARY.md)** - RBAC fixes applied
- **[RBAC Tenant Isolation](implementation/RBAC_TENANT_ISOLATION.md)** - Tenant isolation in RBAC
- **[Tenant Isolation Review](implementation/TENANT_ISOLATION_REVIEW.md)** - Tenant isolation review
- **[Payment Facilitation](implementation/PAYMENT_FACILITATION_IMPLEMENTATION.md)** - Payment implementation
- **[Services Implementation](implementation/SERVICES_IMPLEMENTATION_REVIEW.md)** - Services feature review
- **[Subscription Implementation](implementation/SUBSCRIPTION_IMPLEMENTATION.md)** - Subscription system
- **[PostgreSQL Migration](implementation/MIGRATION_PSYCOPG3.md)** - psycopg3 migration guide

## ⚙️ Setup & Configuration

- **[Fixes Summary](setup/FIXES_SUMMARY.md)** - Recent fixes and improvements
- **[Setup Complete](setup/SETUP_COMPLETE.md)** - Setup completion guide
- **[Setup Success](setup/SETUP_SUCCESS.md)** - Setup verification

## 📝 Other

- **[Changelog](CHANGELOG.md)** - Version history and changes
- **[Deployment Summary](DEPLOYMENT_SUMMARY.txt)** - Deployment documentation summary

---

## Documentation Structure

```
docs/
├── README.md                          # This file
├── QUICKSTART_DEPLOYMENT.md           # Quick start (10 min)
├── DEPLOYMENT.md                      # Full deployment guide
├── DEPLOYMENT_CHECKLIST.md            # Deployment checklist
├── DEPLOYMENT_DOCS_INDEX.md           # Complete index
├── ENVIRONMENT_VARIABLES.md           # Environment variables
├── STARTUP_VALIDATION.md              # Security validation on startup
├── DATABASE_MIGRATIONS.md             # Database migrations
├── MONITORING_SETUP.md                # Monitoring setup
├── TWILIO_WEBHOOK_SETUP.md            # Twilio webhooks
├── CHANGELOG.md                       # Version history
├── DEPLOYMENT_SUMMARY.txt             # Summary
│
├── api/                               # API Documentation
│   ├── API_QUICK_REFERENCE.md
│   ├── OPENAPI_RBAC_GUIDE.md
│   ├── POSTMAN_GUIDE.md
│   ├── POSTMAN_README.md
│   ├── POSTMAN_TEST_SCENARIOS.md
│   └── POSTMAN_COLLECTION_SUMMARY.md
│
├── conversational-commerce-ux-enhancement/  # UX Enhancement Feature
│   ├── README.md                      # Feature documentation index
│   ├── API_DOCUMENTATION.md           # Technical API reference
│   ├── USER_GUIDE.md                  # End-user guide
│   ├── ADMIN_GUIDE.md                 # Admin configuration guide
│   ├── DEPLOYMENT_CHECKLIST.md        # Deployment procedures
│   └── ROLLBACK_PLAN.md               # Rollback procedures
│
├── guides/                            # User Guides
│   ├── DEMO_DATA_GUIDE.md
│   └── QUICKSTART.md
│
├── implementation/                    # Implementation Details
│   ├── RBAC_AUDIT_REPORT.md
│   ├── RBAC_FIX_SUMMARY.md
│   ├── RBAC_TENANT_ISOLATION.md
│   ├── TENANT_ISOLATION_REVIEW.md
│   ├── PAYMENT_FACILITATION_IMPLEMENTATION.md
│   ├── SERVICES_IMPLEMENTATION_REVIEW.md
│   ├── SUBSCRIPTION_IMPLEMENTATION.md
│   └── MIGRATION_PSYCOPG3.md
│
├── monitoring/                        # Monitoring Documentation
│   ├── MONITORING_IMPLEMENTATION_SUMMARY.md
│   ├── MONITORING.md
│   └── MONITORING_QUICK_START.md
│
└── setup/                             # Setup Documentation
    ├── FIXES_SUMMARY.md
    ├── SETUP_COMPLETE.md
    └── SETUP_SUCCESS.md
```

---

## Getting Help

- **Quick Start**: Start with [QUICKSTART_DEPLOYMENT.md](QUICKSTART_DEPLOYMENT.md)
- **Deployment Issues**: See [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
- **API Questions**: Check [api/API_QUICK_REFERENCE.md](api/API_QUICK_REFERENCE.md)
- **Monitoring**: See [MONITORING_SETUP.md](MONITORING_SETUP.md)

---

**Last Updated**: 2025-01-20
