#!/usr/bin/env python
"""
Comprehensive security audit script.

Checks for common security vulnerabilities and misconfigurations.
"""
import os
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class SecurityAudit:
    """Comprehensive security audit."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def add_issue(self, category, message, severity='HIGH'):
        """Add a security issue."""
        self.issues.append({
            'category': category,
            'message': message,
            'severity': severity
        })
    
    def add_warning(self, category, message):
        """Add a security warning."""
        self.warnings.append({
            'category': category,
            'message': message
        })
    
    def add_passed(self, category, message):
        """Add a passed check."""
        self.passed.append({
            'category': category,
            'message': message
        })
    
    def check_secret_keys(self):
        """Check secret key configuration."""
        print("\n[*] Checking secret keys...")
        
        # Check SECRET_KEY
        if not settings.SECRET_KEY:
            self.add_issue('SECRET_KEY', 'SECRET_KEY is not set', 'CRITICAL')
        elif len(settings.SECRET_KEY) < 50:
            self.add_issue('SECRET_KEY', f'SECRET_KEY is too short ({len(settings.SECRET_KEY)} chars, need ≥50)', 'HIGH')
        elif settings.SECRET_KEY == 'your-secret-key-here-change-in-production':
            self.add_issue('SECRET_KEY', 'SECRET_KEY is using default value', 'CRITICAL')
        else:
            self.add_passed('SECRET_KEY', 'SECRET_KEY is properly configured')
        
        # Check JWT_SECRET_KEY
        jwt_key = getattr(settings, 'JWT_SECRET_KEY', None)
        if not jwt_key:
            self.add_issue('JWT_SECRET_KEY', 'JWT_SECRET_KEY is not set', 'CRITICAL')
        elif len(jwt_key) < 32:
            self.add_issue('JWT_SECRET_KEY', f'JWT_SECRET_KEY is too short ({len(jwt_key)} chars, need ≥32)', 'HIGH')
        elif jwt_key == settings.SECRET_KEY:
            self.add_issue('JWT_SECRET_KEY', 'JWT_SECRET_KEY is same as SECRET_KEY', 'HIGH')
        else:
            self.add_passed('JWT_SECRET_KEY', 'JWT_SECRET_KEY is properly configured')
        
        # Check ENCRYPTION_KEY
        enc_key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not enc_key:
            self.add_issue('ENCRYPTION_KEY', 'ENCRYPTION_KEY is not set', 'CRITICAL')
        else:
            self.add_passed('ENCRYPTION_KEY', 'ENCRYPTION_KEY is configured')
    
    def check_https_settings(self):
        """Check HTTPS configuration."""
        print("\n[*] Checking HTTPS settings...")
        
        if settings.DEBUG:
            self.add_warning('HTTPS', 'DEBUG=True, HTTPS checks skipped for development')
            return
        
        if not settings.SECURE_SSL_REDIRECT:
            self.add_issue('HTTPS', 'SECURE_SSL_REDIRECT is not enabled in production', 'HIGH')
        else:
            self.add_passed('HTTPS', 'HTTPS redirect is enabled')
        
        if settings.SECURE_HSTS_SECONDS == 0:
            self.add_issue('HTTPS', 'HSTS is not enabled', 'MEDIUM')
        elif settings.SECURE_HSTS_SECONDS < 31536000:
            self.add_warning('HTTPS', f'HSTS duration is short ({settings.SECURE_HSTS_SECONDS}s, recommend 31536000s)')
        else:
            self.add_passed('HTTPS', 'HSTS is properly configured')
        
        if not settings.SESSION_COOKIE_SECURE:
            self.add_issue('HTTPS', 'SESSION_COOKIE_SECURE is not enabled', 'HIGH')
        else:
            self.add_passed('HTTPS', 'Secure session cookies enabled')
        
        if not settings.CSRF_COOKIE_SECURE:
            self.add_issue('HTTPS', 'CSRF_COOKIE_SECURE is not enabled', 'HIGH')
        else:
            self.add_passed('HTTPS', 'Secure CSRF cookies enabled')
    
    def check_cors_settings(self):
        """Check CORS configuration."""
        print("\n[*] Checking CORS settings...")
        
        if settings.DEBUG:
            if settings.CORS_ALLOW_ALL_ORIGINS:
                self.add_passed('CORS', 'CORS allows all origins in development (OK)')
            return
        
        if settings.CORS_ALLOW_ALL_ORIGINS:
            self.add_issue('CORS', 'CORS_ALLOW_ALL_ORIGINS=True in production', 'CRITICAL')
        else:
            self.add_passed('CORS', 'CORS does not allow all origins')
        
        origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        if not origins:
            self.add_warning('CORS', 'No CORS origins configured')
        else:
            for origin in origins:
                if not origin.startswith('https://'):
                    self.add_issue('CORS', f'Non-HTTPS CORS origin: {origin}', 'HIGH')
            if all(o.startswith('https://') for o in origins):
                self.add_passed('CORS', f'All {len(origins)} CORS origins use HTTPS')
    
    def check_security_headers(self):
        """Check security headers."""
        print("\n[*] Checking security headers...")
        
        if not settings.SECURE_CONTENT_TYPE_NOSNIFF:
            self.add_issue('HEADERS', 'SECURE_CONTENT_TYPE_NOSNIFF is not enabled', 'MEDIUM')
        else:
            self.add_passed('HEADERS', 'Content-Type nosniff enabled')
        
        if not settings.SECURE_BROWSER_XSS_FILTER:
            self.add_issue('HEADERS', 'SECURE_BROWSER_XSS_FILTER is not enabled', 'MEDIUM')
        else:
            self.add_passed('HEADERS', 'XSS filter enabled')
        
        if settings.X_FRAME_OPTIONS != 'DENY':
            self.add_warning('HEADERS', f'X_FRAME_OPTIONS is {settings.X_FRAME_OPTIONS}, recommend DENY')
        else:
            self.add_passed('HEADERS', 'X-Frame-Options set to DENY')
    
    def check_database_security(self):
        """Check database configuration."""
        print("\n[*] Checking database security...")
        
        db_config = settings.DATABASES.get('default', {})
        
        # Check if using SQLite in production
        if not settings.DEBUG and 'sqlite' in db_config.get('ENGINE', '').lower():
            self.add_warning('DATABASE', 'Using SQLite in production (not recommended)')
        
        # Check connection pooling
        if db_config.get('CONN_MAX_AGE', 0) == 0:
            self.add_warning('DATABASE', 'Connection pooling disabled (CONN_MAX_AGE=0)')
        else:
            self.add_passed('DATABASE', f'Connection pooling enabled (CONN_MAX_AGE={db_config.get("CONN_MAX_AGE")})')
    
    def check_password_validators(self):
        """Check password validation."""
        print("\n[*] Checking password validators...")
        
        validators = settings.AUTH_PASSWORD_VALIDATORS
        if not validators:
            self.add_issue('PASSWORD', 'No password validators configured', 'HIGH')
        else:
            validator_types = [v['NAME'].split('.')[-1] for v in validators]
            required = ['UserAttributeSimilarityValidator', 'MinimumLengthValidator', 'CommonPasswordValidator']
            missing = [r for r in required if r not in validator_types]
            if missing:
                self.add_warning('PASSWORD', f'Missing recommended validators: {", ".join(missing)}')
            else:
                self.add_passed('PASSWORD', f'{len(validators)} password validators configured')
    
    def check_admin_security(self):
        """Check Django admin security."""
        print("\n[*] Checking admin security...")
        
        # Check for default admin users
        try:
            admin_users = User.objects.filter(is_superuser=True)
            if admin_users.exists():
                for user in admin_users:
                    if user.email in ['admin@example.com', 'admin@localhost', 'test@test.com']:
                        self.add_issue('ADMIN', f'Default admin email found: {user.email}', 'HIGH')
                self.add_passed('ADMIN', f'{admin_users.count()} superuser(s) configured')
        except Exception as e:
            self.add_warning('ADMIN', f'Could not check admin users: {e}')
    
    def check_debug_mode(self):
        """Check DEBUG mode."""
        print("\n[*] Checking DEBUG mode...")
        
        if settings.DEBUG:
            self.add_warning('DEBUG', 'DEBUG=True (OK for development, MUST be False in production)')
        else:
            self.add_passed('DEBUG', 'DEBUG=False (production mode)')
    
    def check_allowed_hosts(self):
        """Check ALLOWED_HOSTS."""
        print("\n[*] Checking ALLOWED_HOSTS...")
        
        if not settings.ALLOWED_HOSTS:
            self.add_issue('ALLOWED_HOSTS', 'ALLOWED_HOSTS is empty', 'HIGH')
        elif '*' in settings.ALLOWED_HOSTS and not settings.DEBUG:
            self.add_issue('ALLOWED_HOSTS', 'ALLOWED_HOSTS contains wildcard in production', 'HIGH')
        else:
            self.add_passed('ALLOWED_HOSTS', f'{len(settings.ALLOWED_HOSTS)} host(s) configured')
    
    def check_rate_limiting(self):
        """Check rate limiting configuration."""
        print("\n[*] Checking rate limiting...")
        
        rate_limit_enabled = getattr(settings, 'RATE_LIMIT_ENABLED', False)
        if not rate_limit_enabled:
            self.add_warning('RATE_LIMIT', 'Rate limiting is disabled')
        else:
            self.add_passed('RATE_LIMIT', 'Rate limiting is enabled')
    
    def check_sentry(self):
        """Check Sentry configuration."""
        print("\n[*] Checking Sentry...")
        
        sentry_dsn = getattr(settings, 'SENTRY_DSN', None)
        if not sentry_dsn and not settings.DEBUG:
            self.add_warning('SENTRY', 'Sentry not configured (recommended for production)')
        elif sentry_dsn:
            self.add_passed('SENTRY', 'Sentry is configured')
    
    def run_audit(self):
        """Run all security checks."""
        print("="*70)
        print("SECURITY AUDIT")
        print("="*70)
        
        self.check_debug_mode()
        self.check_secret_keys()
        self.check_https_settings()
        self.check_cors_settings()
        self.check_security_headers()
        self.check_database_security()
        self.check_password_validators()
        self.check_admin_security()
        self.check_allowed_hosts()
        self.check_rate_limiting()
        self.check_sentry()
        
        # Print results
        print("\n" + "="*70)
        print("AUDIT RESULTS")
        print("="*70)
        
        if self.issues:
            print(f"\n❌ ISSUES FOUND: {len(self.issues)}")
            for issue in self.issues:
                severity_icon = "🔴" if issue['severity'] == 'CRITICAL' else "🟠" if issue['severity'] == 'HIGH' else "🟡"
                print(f"  {severity_icon} [{issue['severity']}] {issue['category']}: {issue['message']}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  ⚠️  {warning['category']}: {warning['message']}")
        
        if self.passed:
            print(f"\n✅ PASSED: {len(self.passed)}")
            for passed in self.passed:
                print(f"  ✅ {passed['category']}: {passed['message']}")
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Critical/High Issues: {len([i for i in self.issues if i['severity'] in ['CRITICAL', 'HIGH']])}")
        print(f"Medium Issues: {len([i for i in self.issues if i['severity'] == 'MEDIUM'])}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Passed Checks: {len(self.passed)}")
        
        # Exit code
        critical_issues = len([i for i in self.issues if i['severity'] in ['CRITICAL', 'HIGH']])
        if critical_issues > 0:
            print(f"\n❌ AUDIT FAILED: {critical_issues} critical/high issues found")
            return 1
        elif self.issues:
            print(f"\n⚠️  AUDIT WARNING: {len(self.issues)} medium issues found")
            return 0
        else:
            print("\n✅ AUDIT PASSED: No critical issues found")
            return 0


if __name__ == '__main__':
    audit = SecurityAudit()
    exit_code = audit.run_audit()
    sys.exit(exit_code)
