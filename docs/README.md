# WabotIQ Documentation

Comprehensive documentation for the WabotIQ conversational commerce platform.

## 📁 Documentation Structure

### `/architecture` - System Architecture & Design
Core system design, data structures, and architectural decisions.

- **[WABOTIQ_PLATFORM_OVERVIEW.md](architecture/WABOTIQ_PLATFORM_OVERVIEW.md)** - Complete platform overview and architecture
- **[TENANT_DATA_STRUCTURE.md](architecture/TENANT_DATA_STRUCTURE.md)** - Tenant data model and configuration reference
- **[TENANT_DATA_FOR_RAG_AND_CUSTOMER_UNDERSTANDING.md](architecture/TENANT_DATA_FOR_RAG_AND_CUSTOMER_UNDERSTANDING.md)** - RAG system and customer data architecture
- **[RAG_FLOW_DIAGRAM.md](architecture/RAG_FLOW_DIAGRAM.md)** - RAG retrieval flow and diagrams
- **[SECURITY_ANALYSIS.md](architecture/SECURITY_ANALYSIS.md)** - Security architecture and threat analysis
- **[SECURITY_AUDIT_REPORT.md](architecture/SECURITY_AUDIT_REPORT.md)** - Comprehensive security audit findings

### `/guides` - User & Developer Guides
Step-by-step guides for using and integrating with the platform.

- **[AUTHENTICATION_GUIDE.md](guides/AUTHENTICATION_GUIDE.md)** - JWT authentication and API access
- **[PAYMENT_INTEGRATION_SUMMARY.md](guides/PAYMENT_INTEGRATION_SUMMARY.md)** - Payment provider integration (M-Pesa, Paystack, Stripe, Pesapal)
- **[QUICK_REFERENCE.md](guides/QUICK_REFERENCE.md)** - Quick reference for common tasks
- **[QUICK_TEST_REFERENCE.md](guides/QUICK_TEST_REFERENCE.md)** - Testing guide and commands
- **[LANGCHAIN_PINECONE_QUICK_REF.md](guides/LANGCHAIN_PINECONE_QUICK_REF.md)** - LangChain and Pinecone integration guide
- **[MULTILINGUAL_QUICK_START.md](guides/MULTILINGUAL_QUICK_START.md)** - Multi-language support setup
- **[RAG_BABY_MODE_EXPLANATION.md](guides/RAG_BABY_MODE_EXPLANATION.md)** - RAG system explained simply

### `/setup` - Setup & Configuration
Initial setup, configuration, and test data guides.

- **[STARTER_STORE_SETUP.md](setup/STARTER_STORE_SETUP.md)** - Setting up a demo tenant
- **[TEST_USER_SETUP_GUIDE.md](setup/TEST_USER_SETUP_GUIDE.md)** - Creating test users and data
- **[TEST_DATA_SUMMARY.md](setup/TEST_DATA_SUMMARY.md)** - Test data structure and seeding

### `/conversational-commerce-ux-enhancement` - Feature Documentation
Detailed documentation for specific features and enhancements.

## 🚀 Quick Start

1. **New to WabotIQ?** Start with [WABOTIQ_PLATFORM_OVERVIEW.md](architecture/WABOTIQ_PLATFORM_OVERVIEW.md)
2. **Setting up development?** See [STARTER_STORE_SETUP.md](setup/STARTER_STORE_SETUP.md)
3. **Integrating payments?** Check [PAYMENT_INTEGRATION_SUMMARY.md](guides/PAYMENT_INTEGRATION_SUMMARY.md)
4. **Need API access?** Read [AUTHENTICATION_GUIDE.md](guides/AUTHENTICATION_GUIDE.md)

## 🔐 Security Note

All example API keys, tokens, and credentials in this documentation are:
- Sanitized with asterisks (e.g., `sk-proj-***************************`)
- For demonstration purposes only
- Never use example credentials in production

Real credentials should be:
- Stored in `.env` files (never committed to git)
- Encrypted at rest in the database
- Rotated regularly
- Scoped with minimum required permissions

## 📚 Additional Resources

- **API Documentation**: `/schema/swagger/` (when server is running)
- **Postman Collection**: `/postman/postman_collection.json`
- **OpenAPI Schema**: `/schema.yml`
- **Main README**: `../README.md`

## 🤝 Contributing

When adding new documentation:
1. Place in appropriate directory (`architecture`, `guides`, or `setup`)
2. Use clear, descriptive filenames
3. Sanitize all secrets and credentials
4. Update this README with links to new docs
5. Follow existing markdown formatting conventions

## 📝 Documentation Standards

- Use markdown format (`.md`)
- Include table of contents for long documents
- Sanitize all API keys and secrets
- Provide code examples where applicable
- Keep language clear and concise
- Update timestamps when making significant changes

---

**Last Updated**: 2025-12-04  
**Maintained By**: WabotIQ Development Team
