"""
Security event logging for monitoring and alerting.

Logs all security-relevant events including:
- Failed login attempts
- Permission denials
- Rate limit violations
- Invalid webhook signatures
- Four-eyes violations
- Suspicious activity

Critical events are sent to Sentry for immediate alerting.
"""
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('security')


class SecurityLogger:
    """
    Centralized security event logging.
    
    All security events are logged with structured data for analysis.
    Critical events trigger Sentry alerts for immediate response.
    """
    
    @classmethod
    def log_failed_login(
        cls,
        email: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        reason: str = 'invalid_credentials'
    ):
        """
        Log failed login attempt.
        
        Args:
            email: Email address attempted
            ip_address: IP address of request
            user_agent: User agent string
            reason: Reason for failure (invalid_credentials, account_locked, etc.)
        """
        logger.warning(
            "Failed login attempt",
            extra={
                'event_type': 'failed_login',
                'email': email,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'reason': reason,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to Sentry if multiple failures from same IP
        cls._check_brute_force(ip_address, 'login')
    
    @classmethod
    def log_permission_denied(
        cls,
        user_id: str,
        tenant_id: str,
        required_scope: str,
        endpoint: str,
        ip_address: str,
        method: str = 'GET'
    ):
        """
        Log permission denial (403 Forbidden).
        
        Args:
            user_id: User ID attempting access
            tenant_id: Tenant ID
            required_scope: Required permission scope
            endpoint: API endpoint accessed
            ip_address: IP address of request
            method: HTTP method
        """
        logger.warning(
            "Permission denied",
            extra={
                'event_type': 'permission_denied',
                'user_id': user_id,
                'tenant_id': tenant_id,
                'required_scope': required_scope,
                'endpoint': endpoint,
                'method': method,
                'ip_address': ip_address,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def log_rate_limit_exceeded(
        cls,
        identifier: str,
        limit_type: str,
        endpoint: str,
        ip_address: str,
        limit: str
    ):
        """
        Log rate limit violation.
        
        Args:
            identifier: User email, IP, or other identifier
            limit_type: Type of rate limit (login, registration, api, etc.)
            endpoint: API endpoint
            ip_address: IP address
            limit: Rate limit that was exceeded (e.g., "5/min")
        """
        logger.warning(
            "Rate limit exceeded",
            extra={
                'event_type': 'rate_limit_exceeded',
                'identifier': identifier,
                'limit_type': limit_type,
                'endpoint': endpoint,
                'ip_address': ip_address,
                'limit': limit,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to Sentry if excessive rate limiting
        cls._check_rate_limit_abuse(ip_address)
    
    @classmethod
    def log_invalid_webhook_signature(
        cls,
        provider: str,
        tenant_id: str,
        ip_address: str,
        endpoint: str
    ):
        """
        Log invalid webhook signature (potential spoofing attempt).
        
        Args:
            provider: Webhook provider (twilio, woocommerce, shopify)
            tenant_id: Tenant ID
            ip_address: IP address of request
            endpoint: Webhook endpoint
        """
        logger.error(
            "Invalid webhook signature - potential spoofing attempt",
            extra={
                'event_type': 'invalid_webhook_signature',
                'provider': provider,
                'tenant_id': tenant_id,
                'ip_address': ip_address,
                'endpoint': endpoint,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Always send to Sentry - this is a critical security event
        if not settings.DEBUG:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Invalid {provider} webhook signature from {ip_address}",
                    level='error',
                    extras={
                        'provider': provider,
                        'tenant_id': tenant_id,
                        'ip_address': ip_address,
                        'endpoint': endpoint
                    }
                )
            except Exception:
                pass
    
    @classmethod
    def log_four_eyes_violation(
        cls,
        user_id: str,
        tenant_id: str,
        action: str,
        reason: str
    ):
        """
        Log four-eyes validation violation.
        
        Args:
            user_id: User ID attempting action
            tenant_id: Tenant ID
            action: Action attempted (e.g., 'approve_withdrawal')
            reason: Reason for violation (same_user, inactive_user, etc.)
        """
        logger.error(
            "Four-eyes validation violation",
            extra={
                'event_type': 'four_eyes_violation',
                'user_id': user_id,
                'tenant_id': tenant_id,
                'action': action,
                'reason': reason,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to Sentry - this indicates a potential security issue
        if not settings.DEBUG:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Four-eyes violation: {reason}",
                    level='warning',
                    extras={
                        'user_id': user_id,
                        'tenant_id': tenant_id,
                        'action': action,
                        'reason': reason
                    }
                )
            except Exception:
                pass
    
    @classmethod
    def log_suspicious_activity(
        cls,
        activity_type: str,
        user_id: Optional[str],
        tenant_id: Optional[str],
        ip_address: str,
        details: Dict[str, Any]
    ):
        """
        Log suspicious activity for investigation.
        
        Args:
            activity_type: Type of suspicious activity
            user_id: User ID (if authenticated)
            tenant_id: Tenant ID (if applicable)
            ip_address: IP address
            details: Additional details about the activity
        """
        logger.warning(
            f"Suspicious activity detected: {activity_type}",
            extra={
                'event_type': 'suspicious_activity',
                'activity_type': activity_type,
                'user_id': user_id,
                'tenant_id': tenant_id,
                'ip_address': ip_address,
                'details': details,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def log_account_lockout(
        cls,
        email: str,
        ip_address: str,
        reason: str = 'too_many_failed_attempts'
    ):
        """
        Log account lockout event.
        
        Args:
            email: Email address of locked account
            ip_address: IP address
            reason: Reason for lockout
        """
        logger.warning(
            "Account locked out",
            extra={
                'event_type': 'account_lockout',
                'email': email,
                'ip_address': ip_address,
                'reason': reason,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def log_password_reset_request(
        cls,
        email: str,
        ip_address: str,
        success: bool
    ):
        """
        Log password reset request.
        
        Args:
            email: Email address
            ip_address: IP address
            success: Whether email was sent
        """
        logger.info(
            "Password reset requested",
            extra={
                'event_type': 'password_reset_request',
                'email': email,
                'ip_address': ip_address,
                'success': success,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def log_email_verification_attempt(
        cls,
        email: str,
        ip_address: str,
        success: bool,
        reason: Optional[str] = None
    ):
        """
        Log email verification attempt.
        
        Args:
            email: Email address
            ip_address: IP address
            success: Whether verification succeeded
            reason: Reason for failure (if applicable)
        """
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            "Email verification attempt",
            extra={
                'event_type': 'email_verification',
                'email': email,
                'ip_address': ip_address,
                'success': success,
                'reason': reason,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def log_api_key_usage(
        cls,
        tenant_id: str,
        api_key_name: str,
        endpoint: str,
        ip_address: str,
        success: bool
    ):
        """
        Log API key usage for audit trail.
        
        Args:
            tenant_id: Tenant ID
            api_key_name: Name of API key used
            endpoint: API endpoint accessed
            ip_address: IP address
            success: Whether request succeeded
        """
        logger.info(
            "API key used",
            extra={
                'event_type': 'api_key_usage',
                'tenant_id': tenant_id,
                'api_key_name': api_key_name,
                'endpoint': endpoint,
                'ip_address': ip_address,
                'success': success,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    # Helper methods for detecting patterns
    
    @classmethod
    def _check_brute_force(cls, ip_address: str, attack_type: str):
        """
        Check for brute force attack patterns.
        
        Sends Sentry alert if threshold exceeded.
        """
        from django.core.cache import cache
        
        cache_key = f"security:brute_force:{attack_type}:{ip_address}"
        count = cache.get(cache_key, 0)
        count += 1
        cache.set(cache_key, count, 3600)  # 1 hour window
        
        # Alert if more than 10 failures in 1 hour
        if count >= 10 and not settings.DEBUG:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Potential brute force attack from {ip_address}",
                    level='warning',
                    extras={
                        'ip_address': ip_address,
                        'attack_type': attack_type,
                        'failure_count': count
                    }
                )
            except Exception:
                pass
    
    @classmethod
    def _check_rate_limit_abuse(cls, ip_address: str):
        """
        Check for rate limit abuse patterns.
        
        Sends Sentry alert if threshold exceeded.
        """
        from django.core.cache import cache
        
        cache_key = f"security:rate_limit_abuse:{ip_address}"
        count = cache.get(cache_key, 0)
        count += 1
        cache.set(cache_key, count, 3600)  # 1 hour window
        
        # Alert if more than 50 rate limit violations in 1 hour
        if count >= 50 and not settings.DEBUG:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Excessive rate limiting from {ip_address}",
                    level='warning',
                    extras={
                        'ip_address': ip_address,
                        'violation_count': count
                    }
                )
            except Exception:
                pass


# Convenience functions for common use cases

def log_failed_login(email: str, ip_address: str, **kwargs):
    """Convenience function for logging failed login."""
    SecurityLogger.log_failed_login(email, ip_address, **kwargs)


def log_permission_denied(user_id: str, tenant_id: str, required_scope: str, **kwargs):
    """Convenience function for logging permission denial."""
    SecurityLogger.log_permission_denied(user_id, tenant_id, required_scope, **kwargs)


def log_rate_limit_exceeded(identifier: str, limit_type: str, **kwargs):
    """Convenience function for logging rate limit violation."""
    SecurityLogger.log_rate_limit_exceeded(identifier, limit_type, **kwargs)


def log_invalid_webhook_signature(provider: str, tenant_id: str, ip_address: str, **kwargs):
    """Convenience function for logging invalid webhook signature."""
    SecurityLogger.log_invalid_webhook_signature(provider, tenant_id, ip_address, **kwargs)


def log_four_eyes_violation(user_id: str, tenant_id: str, action: str, reason: str):
    """Convenience function for logging four-eyes violation."""
    SecurityLogger.log_four_eyes_violation(user_id, tenant_id, action, reason)
