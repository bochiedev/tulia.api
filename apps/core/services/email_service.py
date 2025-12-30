"""
Platform email service with provider abstraction.

Supports multiple email providers through platform settings:
- SendGrid
- AWS SES (future)
- Mailgun (future)
- Console (development)
"""
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.mail import send_mail as django_send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from apps.core.platform_settings import PlatformSettings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors."""
    pass


class EmailService:
    """
    Platform email service with provider abstraction.
    
    Automatically uses the configured email provider from platform settings.
    Supports HTML templates, attachments, and multiple recipients.
    """
    
    @classmethod
    def send_email(
        cls,
        to_emails: List[str],
        subject: str,
        template_name: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        fail_silently: bool = False
    ) -> bool:
        """
        Send email using the configured provider.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject line
            template_name: Optional template name (without .html extension)
            template_context: Context variables for template rendering
            html_content: Raw HTML content (if not using template)
            text_content: Raw text content (if not using template)
            from_email: Sender email (uses platform default if not provided)
            reply_to: Reply-to email address
            fail_silently: Whether to suppress exceptions
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Get email configuration
            email_config = PlatformSettings.get_email_config()
            provider = email_config['provider']
            
            # Use provided from_email or platform default
            if not from_email:
                from_email = email_config['from_email']
            
            # Prepare email content
            if template_name:
                html_content, text_content = cls._render_template(
                    template_name, template_context or {}
                )
            elif not html_content and not text_content:
                raise EmailServiceError("Either template_name or content must be provided")
            
            # Generate text content from HTML if not provided
            if html_content and not text_content:
                text_content = strip_tags(html_content)
            
            # Send based on provider
            if provider == 'sendgrid':
                return cls._send_via_sendgrid(
                    to_emails=to_emails,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email,
                    reply_to=reply_to,
                    api_key=email_config.get('api_key', '')
                )
            elif provider == 'console':
                return cls._send_via_console(
                    to_emails=to_emails,
                    subject=subject,
                    text_content=text_content,
                    from_email=from_email
                )
            else:
                # Fallback to Django's default email backend
                return cls._send_via_django(
                    to_emails=to_emails,
                    subject=subject,
                    text_content=text_content,
                    from_email=from_email,
                    fail_silently=fail_silently
                )
                
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            if not fail_silently:
                raise EmailServiceError(f"Email sending failed: {e}")
            return False
    
    @classmethod
    def _render_template(cls, template_name: str, context: Dict[str, Any]) -> tuple:
        """
        Render HTML and text email templates.
        
        Args:
            template_name: Template name without extension
            context: Template context variables
            
        Returns:
            Tuple of (html_content, text_content)
        """
        try:
            # Add platform context
            platform_context = {
                'platform_name': 'Tulia AI',
                'platform_url': getattr(settings, 'FRONTEND_URL', 'https://trytulia.com'),
                'support_email': 'support@trytulia.com',
                **context
            }
            
            # Render HTML template
            html_template = f'emails/{template_name}.html'
            html_content = render_to_string(html_template, platform_context)
            
            # Try to render text template, fallback to HTML stripped
            try:
                text_template = f'emails/{template_name}.txt'
                text_content = render_to_string(text_template, platform_context)
            except:
                text_content = strip_tags(html_content)
            
            return html_content, text_content
            
        except Exception as e:
            logger.error(f"Failed to render email template '{template_name}': {e}")
            raise EmailServiceError(f"Template rendering failed: {e}")
    
    @classmethod
    def _send_via_sendgrid(
        cls,
        to_emails: List[str],
        subject: str,
        html_content: Optional[str],
        text_content: Optional[str],
        from_email: str,
        reply_to: Optional[str],
        api_key: str
    ) -> bool:
        """Send email via SendGrid API."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            if not api_key:
                raise EmailServiceError("SendGrid API key not configured")
            
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            
            # Create email
            from_email_obj = Email(from_email)
            to_list = [To(email) for email in to_emails]
            
            # Create content
            content_list = []
            if text_content:
                content_list.append(Content("text/plain", text_content))
            if html_content:
                content_list.append(Content("text/html", html_content))
            
            # Send to each recipient (SendGrid handles this efficiently)
            for to_email in to_list:
                mail = Mail(
                    from_email=from_email_obj,
                    to_emails=to_email,
                    subject=subject,
                    html_content=html_content,
                    plain_text_content=text_content
                )
                
                if reply_to:
                    mail.reply_to = Email(reply_to)
                
                response = sg.send(mail)
                
                if response.status_code not in [200, 201, 202]:
                    logger.error(f"SendGrid API error: {response.status_code} - {response.body}")
                    return False
            
            logger.info(f"Email sent via SendGrid to {len(to_emails)} recipients")
            return True
            
        except ImportError:
            logger.error("SendGrid library not installed. Run: pip install sendgrid")
            return False
        except Exception as e:
            logger.error(f"SendGrid sending failed: {e}")
            return False
    
    @classmethod
    def _send_via_console(
        cls,
        to_emails: List[str],
        subject: str,
        text_content: str,
        from_email: str
    ) -> bool:
        """Send email via console (development mode)."""
        try:
            print("\n" + "="*60)
            print("📧 EMAIL (Console Mode)")
            print("="*60)
            print(f"From: {from_email}")
            print(f"To: {', '.join(to_emails)}")
            print(f"Subject: {subject}")
            print("-"*60)
            print(text_content)
            print("="*60)
            
            logger.info(f"Email logged to console for {len(to_emails)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Console email logging failed: {e}")
            return False
    
    @classmethod
    def _send_via_django(
        cls,
        to_emails: List[str],
        subject: str,
        text_content: str,
        from_email: str,
        fail_silently: bool = False
    ) -> bool:
        """Send email via Django's default email backend."""
        try:
            django_send_mail(
                subject=subject,
                message=text_content,
                from_email=from_email,
                recipient_list=to_emails,
                fail_silently=fail_silently
            )
            
            logger.info(f"Email sent via Django backend to {len(to_emails)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Django email sending failed: {e}")
            return False


# Convenience functions for common email types
def send_welcome_email(user_email: str, user_name: str, verification_url: str) -> bool:
    """Send welcome email with verification link."""
    return EmailService.send_email(
        to_emails=[user_email],
        subject="Welcome to Tulia AI - Verify Your Email",
        template_name="welcome_verification",
        template_context={
            'user_name': user_name,
            'user_email': user_email,
            'verification_url': verification_url,
        }
    )


def send_email_verification(user_email: str, user_name: str, verification_url: str) -> bool:
    """Send email verification (for existing users)."""
    return EmailService.send_email(
        to_emails=[user_email],
        subject="Verify Your Email Address",
        template_name="email_verification",
        template_context={
            'user_name': user_name,
            'user_email': user_email,
            'verification_url': verification_url,
        }
    )


def send_password_reset_email(user_email: str, user_name: str, reset_url: str) -> bool:
    """Send password reset email."""
    return EmailService.send_email(
        to_emails=[user_email],
        subject="Reset Your Password - Tulia AI",
        template_name="password_reset",
        template_context={
            'user_name': user_name,
            'user_email': user_email,
            'reset_url': reset_url,
        }
    )


def send_tenant_invitation_email(
    user_email: str, 
    user_name: str, 
    tenant_name: str, 
    inviter_name: str,
    invitation_url: str
) -> bool:
    """Send tenant invitation email."""
    return EmailService.send_email(
        to_emails=[user_email],
        subject=f"You've been invited to join {tenant_name}",
        template_name="tenant_invitation",
        template_context={
            'user_name': user_name,
            'user_email': user_email,
            'tenant_name': tenant_name,
            'inviter_name': inviter_name,
            'invitation_url': invitation_url,
        }
    )