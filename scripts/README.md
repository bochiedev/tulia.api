# TuliaAI Utility Scripts

This directory contains utility scripts for TuliaAI development and deployment.

## Security Scripts

### `generate_secrets.py`

Generates cryptographically secure keys for TuliaAI configuration.

**Usage:**
```bash
python scripts/generate_secrets.py
```

**Generates:**
- `SECRET_KEY` - Django secret key for cryptographic signing
- `JWT_SECRET_KEY` - JWT token signing key (must be different from SECRET_KEY)
- `ENCRYPTION_KEY` - 32-byte base64-encoded key for data encryption

**Features:**
- Validates key strength (length and entropy)
- Ensures all keys are unique
- Provides security warnings and best practices
- Output is ready to copy into `.env` file

**Security Notes:**
- Never commit generated keys to version control
- Use different keys for each environment (dev, staging, production)
- Rotate keys periodically, especially after security incidents
- Store keys securely in environment-specific `.env` files

### `rotate_jwt_secret.py`

Rotates the JWT secret key to invalidate all existing tokens.

**Usage:**
```bash
# Interactive mode (recommended)
python scripts/rotate_jwt_secret.py

# Non-interactive mode
python scripts/rotate_jwt_secret.py --force

# Auto-update .env file
python scripts/rotate_jwt_secret.py --force --auto-update-env
```

**What it does:**
- Generates a new cryptographically secure JWT secret key
- Validates the new key meets security requirements
- Shows impact of rotation (affected users, systems)
- Optionally updates .env file automatically
- Clears user sessions from cache
- Provides comprehensive pre/post-rotation checklists

**When to use:**
- After JWT tokens are exposed or leaked
- As part of regular security maintenance (every 90 days)
- After a security incident
- When rotating all credentials

**Impact:**
- All existing JWT tokens immediately invalidated
- All users must log in again
- API integrations need new tokens
- Mobile apps need re-authentication

**See also:** 
- `.kiro/specs/security-remediation/JWT_ROTATION_GUIDE.md` - Comprehensive guide
- `.kiro/specs/security-remediation/JWT_ROTATION_QUICK_REFERENCE.md` - Quick reference

### `rotate_api_keys.py`

Rotates all exposed API keys (third-party services and tenant API keys).

**Usage:**
```bash
# Show what would be rotated (dry run)
python scripts/rotate_api_keys.py --dry-run

# Rotate tenant API keys only
python scripts/rotate_api_keys.py --tenant-keys-only

# Full rotation with instructions for third-party keys
python scripts/rotate_api_keys.py
```

**What it does:**
- Provides instructions for rotating third-party API keys (OpenAI, SendGrid, Sentry)
- Automatically rotates tenant API keys in the database
- Revokes old tenant API keys
- Generates new tenant API keys
- Provides verification checklist

**When to use:**
- After API keys are exposed in git repository
- As part of security incident response
- During regular security maintenance
- After employee departures

**Impact:**
- Third-party services: Must be rotated manually in service dashboards
- Tenant API keys: Automatically rotated, all API clients must be updated
- Application restart required after updating .env file

**See also:**
- `.kiro/specs/security-remediation/API_KEY_ROTATION_GUIDE.md` - Comprehensive guide
- `.kiro/specs/security-remediation/API_KEY_ROTATION_QUICK_REFERENCE.md` - Quick reference
- `.kiro/specs/security-remediation/HARDCODED_SECRETS_AUDIT.md` - Audit report

### `verify_jwt_rotation.sh`

Verifies that JWT token rotation has been completed successfully.

**Usage:**
```bash
./scripts/verify_jwt_rotation.sh
```

**What it checks:**
- Hardcoded tokens removed from all files
- Rotation script exists and is executable
- Documentation is in place
- JWT configuration is correct
- .env.example is properly documented
- Postman environment is clean
- Git history status (warning only)

**Exit codes:**
- `0` - All checks passed
- `1` - One or more checks failed

**See also:** `.kiro/specs/security-remediation/TASK_1.5_JWT_ROTATION_SUMMARY.md`

### `clean_git_history.sh`

Removes sensitive files from git history using BFG Repo-Cleaner (interactive version).

**Usage:**
```bash
./scripts/clean_git_history.sh
```

**What it does:**
- Creates a backup of the repository
- Downloads BFG Repo-Cleaner (if not present)
- Removes specified files from all git history
- Cleans up the repository with `git gc`
- Verifies files are removed
- Provides next steps for team coordination

**Files removed:**
- `.env` - Production secrets
- `test_all_auth.py` - Hardcoded JWT tokens
- `test_auth_endpoint.py` - Hardcoded JWT tokens
- `comprehensive_api_test.py` - Hardcoded credentials
- `test_api_fixes.sh` - Hardcoded API keys

**⚠️ Warnings:**
- Rewrites git history (all commit hashes change)
- Requires force-push to remote
- All team members must re-clone after execution
- Cannot be undone once pushed to remote

**Prerequisites:**
- Java installed (for running BFG)
- Git repository with committed changes
- Sufficient disk space for backup

**See also:** `.kiro/specs/security-remediation/GIT_HISTORY_CLEANUP_GUIDE.md` for detailed documentation

### `clean_git_history_auto.sh`

Automated version of git history cleanup (non-interactive, for CI/CD).

**Usage:**
```bash
./scripts/clean_git_history_auto.sh
```

**Differences from interactive version:**
- No user prompts or confirmations
- No backup creation (assumes external backup)
- Quieter output
- Suitable for automated workflows

### `setup_ci_secrets.sh`

Interactive script to help set up CI/CD secrets for GitHub Actions or GitLab CI.

**Usage:**
```bash
./scripts/setup_ci_secrets.sh
```

**What it does:**
- Generates secure keys for all environments (CI, staging, production)
- Creates a secrets file with all required environment variables
- Provides platform-specific setup instructions
- Automatically adds secrets file pattern to .gitignore
- Includes comprehensive security warnings

**Supports:**
- GitHub Actions (with environment protection)
- GitLab CI (with variable scoping)
- Generic secrets file generation

**Generated secrets include:**
- Django SECRET_KEY and JWT_SECRET_KEY
- Encryption keys
- Database connection strings
- Redis URLs
- Payment provider keys (Stripe, Paystack, M-Pesa, etc.)
- Email configuration
- Sentry DSN
- SSH keys for deployment

**Security Notes:**
- Generated secrets file must be deleted after use
- Never commit secrets file to version control
- Review and update all placeholder values
- Use different keys for each environment

**See also:** `docs/CI_CD_SETUP.md` for complete CI/CD configuration guide

### `install_git_hooks.sh`

Installs the pre-commit hook for automatic secret detection.

**Usage:**
```bash
./scripts/install_git_hooks.sh
```

**What it does:**
- Installs the pre-commit hook to `.git/hooks/pre-commit`
- Backs up any existing hook
- Makes the hook executable
- Tests the hook installation
- Provides usage instructions

**When to use:**
- Initial repository setup
- After cloning the repository
- After updating the hook script
- When setting up a new development machine

**What the hook does:**
- Scans all staged files for secrets before commit
- Detects API keys, tokens, private keys, passwords
- Blocks commits containing secrets
- Provides clear error messages and remediation steps
- Can be bypassed with `--no-verify` (use with caution)

**Detected patterns:**
- API keys (AWS, Stripe, OpenAI, GitHub, etc.)
- JWT tokens
- Private keys and certificates
- Database connection strings
- Hardcoded passwords and tokens
- Sensitive filenames (.env, *.key, *.pem, etc.)

**See also:** 
- `.kiro/specs/security-remediation/SECRET_MANAGEMENT.md` - Complete secret management guide
- `scripts/pre-commit-hook.sh` - The actual hook script

## Development Scripts

### `seed_realistic_demo.py`

Seeds the database with realistic demo data for testing and development.

**Usage:**
```bash
python manage.py shell < scripts/seed_realistic_demo.py
```

### `generate_postman_collection.py`

Generates a Postman collection from the OpenAPI schema.

**Usage:**
```bash
python scripts/generate_postman_collection.py
```

## Setup Scripts

### `setup.sh`

Initial setup script for development environment.

**Usage:**
```bash
bash scripts/setup.sh
```

## Contributing

When adding new scripts:
1. Add a shebang line (`#!/usr/bin/env python3` or `#!/bin/bash`)
2. Make the script executable: `chmod +x scripts/your_script.py`
3. Add comprehensive docstrings/comments
4. Update this README with usage instructions
5. Test the script in a clean environment
