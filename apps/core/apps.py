from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'

    def ready(self):
        """
        Perform startup validation checks when Django initializes.
        
        This ensures critical security configurations are properly set
        before the application starts accepting requests.
        """
        # Only run validation once (not in every worker/thread)
        import sys
        if 'runserver' not in sys.argv and 'gunicorn' not in sys.argv[0]:
            # Skip validation for management commands (except runserver)
            # This allows migrations, shell, etc. to run without full config
            if len(sys.argv) > 1 and sys.argv[1] not in ['runserver', 'test']:
                return
        
        self._validate_jwt_configuration()
        self._validate_encryption_configuration()
        self._validate_security_settings()
        
        logger.info("✓ All startup security validations passed")

    def _validate_jwt_configuration(self):
        """Validate JWT secret key configuration."""
        jwt_secret = getattr(settings, 'JWT_SECRET_KEY', None)
        secret_key = getattr(settings, 'SECRET_KEY', None)
        
        # JWT_SECRET_KEY must be set
        if not jwt_secret:
            raise ImproperlyConfigured(
                "JWT_SECRET_KEY must be set in environment variables. "
                "Generate a strong key with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # JWT_SECRET_KEY must be at least 32 characters
        if len(jwt_secret) < 32:
            raise ImproperlyConfigured(
                f"JWT_SECRET_KEY must be at least 32 characters long for security. "
                f"Current length: {len(jwt_secret)}. "
                f"Generate a strong key with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # JWT_SECRET_KEY must differ from SECRET_KEY
        if jwt_secret == secret_key:
            raise ImproperlyConfigured(
                "JWT_SECRET_KEY must be different from SECRET_KEY for security. "
                "Using the same key for both purposes weakens security. "
                "Generate a separate JWT key with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # Validate entropy
        unique_chars = len(set(jwt_secret))
        if unique_chars < 16:
            raise ImproperlyConfigured(
                f"JWT_SECRET_KEY has insufficient entropy. "
                f"Found only {unique_chars} unique characters, need at least 16. "
                f"Generate a strong key with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # Check for simple repeating patterns
        if len(jwt_secret) >= 4:
            # Check if key is just one character repeated
            if jwt_secret == jwt_secret[0] * len(jwt_secret):
                raise ImproperlyConfigured(
                    "JWT_SECRET_KEY is a repeating character pattern. "
                    "Generate a strong key with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            
            # Check for simple 2-character patterns
            if len(jwt_secret) >= 6:
                pattern = jwt_secret[:2]
                expected = pattern * (len(jwt_secret) // len(pattern)) + pattern[:len(jwt_secret) % len(pattern)]
                if jwt_secret == expected:
                    raise ImproperlyConfigured(
                        "JWT_SECRET_KEY is a simple repeating pattern. "
                        "Generate a strong key with: "
                        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                    )
        
        logger.info("✓ JWT configuration validated")

    def _validate_encryption_configuration(self):
        """Validate encryption key configuration."""
        encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
        
        if not encryption_key:
            # Encryption key is optional, but warn if not set
            logger.warning(
                "⚠ ENCRYPTION_KEY is not set. Sensitive data will not be encrypted. "
                "Generate a key with: "
                "python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
            )
            return
        
        # Validate encryption key format (should be base64-encoded 32 bytes)
        try:
            import base64
            decoded = base64.b64decode(encryption_key)
            
            if len(decoded) != 32:
                raise ImproperlyConfigured(
                    f"ENCRYPTION_KEY must be exactly 32 bytes when decoded. "
                    f"Current length: {len(decoded)} bytes. "
                    f"Generate a valid key with: "
                    f"python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
                )
            
            # Check for weak keys
            unique_bytes = len(set(decoded))
            if unique_bytes < 16:
                raise ImproperlyConfigured(
                    f"ENCRYPTION_KEY has insufficient entropy. "
                    f"Found only {unique_bytes} unique bytes, need at least 16. "
                    f"Generate a strong key with: "
                    f"python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
                )
            
            # Check for all-zero key
            if decoded == b'\x00' * 32:
                raise ImproperlyConfigured(
                    "ENCRYPTION_KEY is all zeros. "
                    "Generate a strong key with: "
                    "python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
                )
            
            logger.info("✓ Encryption configuration validated")
            
        except Exception as e:
            if isinstance(e, ImproperlyConfigured):
                raise
            raise ImproperlyConfigured(
                f"ENCRYPTION_KEY is not valid base64: {e}. "
                f"Generate a valid key with: "
                f"python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
            )

    def _validate_security_settings(self):
        """Validate general security settings."""
        debug = getattr(settings, 'DEBUG', False)
        secret_key = getattr(settings, 'SECRET_KEY', None)
        
        # SECRET_KEY must be set
        if not secret_key:
            raise ImproperlyConfigured(
                "SECRET_KEY must be set in environment variables. "
                "Generate with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(50))\""
            )
        
        # Warn about weak SECRET_KEY
        if len(secret_key) < 50:
            logger.warning(
                f"⚠ SECRET_KEY is shorter than recommended (current: {len(secret_key)}, recommended: 50+). "
                f"Generate a stronger key with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(50))\""
            )
        
        # Warn about default/weak keys in production
        if not debug:
            weak_patterns = [
                'your-secret-key',
                'change-me',
                'insecure',
                'django-insecure',
                '12345',
                'password',
                'secret',
            ]
            
            secret_lower = secret_key.lower()
            for pattern in weak_patterns:
                if pattern in secret_lower:
                    raise ImproperlyConfigured(
                        f"SECRET_KEY appears to be a default or weak value (contains '{pattern}'). "
                        f"Generate a strong key with: "
                        f"python -c \"import secrets; print(secrets.token_urlsafe(50))\""
                    )
            
            # Check HTTPS enforcement in production
            if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
                logger.warning(
                    "⚠ SECURE_SSL_REDIRECT is not enabled in production. "
                    "HTTPS should be enforced for security."
                )
            
            # Check secure cookie settings
            if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
                logger.warning(
                    "⚠ SESSION_COOKIE_SECURE is not enabled in production. "
                    "Cookies should only be sent over HTTPS."
                )
            
            if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
                logger.warning(
                    "⚠ CSRF_COOKIE_SECURE is not enabled in production. "
                    "CSRF cookies should only be sent over HTTPS."
                )
        
        logger.info("✓ Security settings validated")
