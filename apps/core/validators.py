"""
Validation utilities for WabotIQ.

Provides credential validation helpers for external services
and common input validation functions.
"""
import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import requests
from requests.auth import HTTPBasicAuth

from apps.core.exceptions import CredentialValidationError

logger = logging.getLogger(__name__)


class CredentialValidator:
    """
    Validates credentials for external services.
    
    Provides methods to test connectivity and validate credentials
    for Twilio, WooCommerce, and Shopify integrations.
    """
    
    @staticmethod
    def validate_twilio_credentials(
        account_sid: str,
        auth_token: str,
        whatsapp_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate Twilio credentials by making a test API call.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            whatsapp_number: Optional WhatsApp number to validate
            
        Returns:
            dict: Validation result with account info
            
        Raises:
            CredentialValidationError: If credentials are invalid
            
        Example:
            >>> result = CredentialValidator.validate_twilio_credentials(
            ...     'AC1234567890abcdef',
            ...     'auth_token_here'
            ... )
            >>> print(result['account_name'])
        """
        try:
            # Create Twilio client
            client = Client(account_sid, auth_token)
            
            # Fetch account details to validate credentials
            account = client.api.accounts(account_sid).fetch()
            
            logger.info(
                f"Twilio credentials validated successfully",
                extra={
                    'account_sid': account_sid,
                    'account_name': account.friendly_name
                }
            )
            
            result = {
                'valid': True,
                'account_sid': account.sid,
                'account_name': account.friendly_name,
                'account_status': account.status,
                'account_type': account.type
            }
            
            # Optionally validate WhatsApp number
            if whatsapp_number:
                try:
                    # Format number for WhatsApp
                    formatted_number = whatsapp_number if whatsapp_number.startswith('whatsapp:') else f'whatsapp:{whatsapp_number}'
                    
                    # Fetch incoming phone numbers to verify ownership
                    incoming_numbers = client.incoming_phone_numbers.list(
                        phone_number=whatsapp_number.replace('whatsapp:', '')
                    )
                    
                    if incoming_numbers:
                        result['whatsapp_number_valid'] = True
                        result['whatsapp_number_sid'] = incoming_numbers[0].sid
                    else:
                        result['whatsapp_number_valid'] = False
                        result['whatsapp_number_warning'] = 'Number not found in account'
                
                except Exception as e:
                    logger.warning(
                        f"Could not validate WhatsApp number",
                        extra={
                            'whatsapp_number': whatsapp_number,
                            'error': str(e)
                        }
                    )
                    result['whatsapp_number_valid'] = False
                    result['whatsapp_number_warning'] = str(e)
            
            return result
        
        except TwilioRestException as e:
            logger.error(
                f"Twilio credential validation failed",
                extra={
                    'account_sid': account_sid,
                    'error_code': e.code,
                    'error_message': str(e)
                },
                exc_info=True
            )
            
            # Provide user-friendly error messages
            if e.code == 20003:
                raise CredentialValidationError(
                    "Authentication failed. Please check your Account SID and Auth Token.",
                    details={'error_code': e.code, 'twilio_message': e.msg}
                )
            elif e.code == 20404:
                raise CredentialValidationError(
                    "Account not found. Please verify your Account SID.",
                    details={'error_code': e.code, 'twilio_message': e.msg}
                )
            else:
                raise CredentialValidationError(
                    f"Twilio API error: {e.msg}",
                    details={'error_code': e.code, 'twilio_message': e.msg}
                )
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating Twilio credentials",
                extra={'account_sid': account_sid},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate Twilio credentials: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def validate_woocommerce_credentials(
        store_url: str,
        consumer_key: str,
        consumer_secret: str
    ) -> Dict[str, Any]:
        """
        Validate WooCommerce credentials by fetching store info.
        
        Args:
            store_url: WooCommerce store URL
            consumer_key: WooCommerce REST API consumer key
            consumer_secret: WooCommerce REST API consumer secret
            
        Returns:
            dict: Validation result with store info
            
        Raises:
            CredentialValidationError: If credentials are invalid
            
        Example:
            >>> result = CredentialValidator.validate_woocommerce_credentials(
            ...     'https://example.com',
            ...     'ck_1234567890',
            ...     'cs_1234567890'
            ... )
            >>> print(result['store_name'])
        """
        try:
            # Normalize store URL
            store_url = store_url.rstrip('/')
            if not store_url.startswith(('http://', 'https://')):
                store_url = f'https://{store_url}'
            
            # Build API endpoint
            api_url = f"{store_url}/wp-json/wc/v3/system_status"
            
            # Make test API call
            auth = HTTPBasicAuth(consumer_key, consumer_secret)
            response = requests.get(api_url, auth=auth, timeout=15)
            
            # Check response status
            if response.status_code == 401:
                raise CredentialValidationError(
                    "Authentication failed. Please check your Consumer Key and Consumer Secret.",
                    details={
                        'status_code': 401,
                        'store_url': store_url
                    }
                )
            elif response.status_code == 404:
                raise CredentialValidationError(
                    "WooCommerce REST API not found. Please ensure WooCommerce is installed and REST API is enabled.",
                    details={
                        'status_code': 404,
                        'store_url': store_url
                    }
                )
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            environment = data.get('environment', {})
            
            logger.info(
                f"WooCommerce credentials validated successfully",
                extra={
                    'store_url': store_url,
                    'store_name': environment.get('site_url')
                }
            )
            
            return {
                'valid': True,
                'store_url': store_url,
                'store_name': environment.get('site_url', store_url),
                'wc_version': environment.get('version'),
                'wp_version': environment.get('wp_version'),
                'permalink_structure': environment.get('permalink_structure')
            }
        
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"WooCommerce credential validation failed",
                extra={
                    'store_url': store_url,
                    'status_code': e.response.status_code,
                    'response': e.response.text
                },
                exc_info=True
            )
            
            raise CredentialValidationError(
                f"WooCommerce API error: {e.response.status_code}",
                details={
                    'status_code': e.response.status_code,
                    'response': e.response.text[:500]
                }
            )
        
        except requests.exceptions.Timeout:
            logger.error(
                f"WooCommerce API timeout",
                extra={'store_url': store_url}
            )
            raise CredentialValidationError(
                "Connection timeout. Please check your store URL and try again.",
                details={'store_url': store_url}
            )
        
        except requests.exceptions.ConnectionError:
            logger.error(
                f"WooCommerce connection error",
                extra={'store_url': store_url}
            )
            raise CredentialValidationError(
                "Could not connect to store. Please verify the store URL is correct.",
                details={'store_url': store_url}
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating WooCommerce credentials",
                extra={'store_url': store_url},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate WooCommerce credentials: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def validate_shopify_credentials(
        shop_domain: str,
        access_token: str
    ) -> Dict[str, Any]:
        """
        Validate Shopify credentials by fetching shop info.
        
        Args:
            shop_domain: Shopify store domain (e.g., mystore.myshopify.com)
            access_token: Shopify Admin API access token
            
        Returns:
            dict: Validation result with shop info
            
        Raises:
            CredentialValidationError: If credentials are invalid
            
        Example:
            >>> result = CredentialValidator.validate_shopify_credentials(
            ...     'mystore.myshopify.com',
            ...     'shpat_1234567890'
            ... )
            >>> print(result['shop_name'])
        """
        try:
            # Normalize shop domain
            shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
            
            # Ensure .myshopify.com domain
            if not shop_domain.endswith('.myshopify.com'):
                # Try to append it
                if '.' not in shop_domain:
                    shop_domain = f"{shop_domain}.myshopify.com"
            
            # Build API endpoint
            api_url = f"https://{shop_domain}/admin/api/2024-01/shop.json"
            
            # Make test API call
            headers = {
                'X-Shopify-Access-Token': access_token,
                'Content-Type': 'application/json'
            }
            response = requests.get(api_url, headers=headers, timeout=15)
            
            # Check response status
            if response.status_code == 401:
                raise CredentialValidationError(
                    "Authentication failed. Please check your Access Token.",
                    details={
                        'status_code': 401,
                        'shop_domain': shop_domain
                    }
                )
            elif response.status_code == 404:
                raise CredentialValidationError(
                    "Shop not found. Please verify your shop domain.",
                    details={
                        'status_code': 404,
                        'shop_domain': shop_domain
                    }
                )
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            shop = data.get('shop', {})
            
            logger.info(
                f"Shopify credentials validated successfully",
                extra={
                    'shop_domain': shop_domain,
                    'shop_name': shop.get('name')
                }
            )
            
            return {
                'valid': True,
                'shop_domain': shop_domain,
                'shop_name': shop.get('name'),
                'shop_owner': shop.get('shop_owner'),
                'email': shop.get('email'),
                'currency': shop.get('currency'),
                'timezone': shop.get('iana_timezone'),
                'plan_name': shop.get('plan_name')
            }
        
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Shopify credential validation failed",
                extra={
                    'shop_domain': shop_domain,
                    'status_code': e.response.status_code,
                    'response': e.response.text
                },
                exc_info=True
            )
            
            raise CredentialValidationError(
                f"Shopify API error: {e.response.status_code}",
                details={
                    'status_code': e.response.status_code,
                    'response': e.response.text[:500]
                }
            )
        
        except requests.exceptions.Timeout:
            logger.error(
                f"Shopify API timeout",
                extra={'shop_domain': shop_domain}
            )
            raise CredentialValidationError(
                "Connection timeout. Please check your shop domain and try again.",
                details={'shop_domain': shop_domain}
            )
        
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Shopify connection error",
                extra={'shop_domain': shop_domain}
            )
            raise CredentialValidationError(
                "Could not connect to shop. Please verify the shop domain is correct.",
                details={'shop_domain': shop_domain}
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating Shopify credentials",
                extra={'shop_domain': shop_domain},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate Shopify credentials: {str(e)}",
                details={'error': str(e)}
            )


class InputValidator:
    """
    Common input validation utilities.
    
    Provides validation methods for email, password, phone numbers,
    URLs, and other common input types.
    """
    
    # Email regex pattern (RFC 5322 simplified)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # E.164 phone number pattern
    PHONE_E164_PATTERN = re.compile(
        r'^\+[1-9]\d{1,14}$'
    )
    
    # URL pattern
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    
    # Hex color pattern
    HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not email:
            return False
        return bool(InputValidator.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength.
        
        Requirements:
        - At least 8 characters
        - Contains uppercase letter
        - Contains lowercase letter
        - Contains digit
        - Contains special character
        
        Args:
            password: Password to validate
            
        Returns:
            dict: Validation result with details
        """
        result = {
            'valid': True,
            'errors': []
        }
        
        if len(password) < 8:
            result['valid'] = False
            result['errors'].append('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', password):
            result['valid'] = False
            result['errors'].append('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', password):
            result['valid'] = False
            result['errors'].append('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', password):
            result['valid'] = False
            result['errors'].append('Password must contain at least one digit')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result['valid'] = False
            result['errors'].append('Password must contain at least one special character')
        
        return result
    
    @staticmethod
    def validate_phone_e164(phone: str) -> bool:
        """
        Validate phone number in E.164 format.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            bool: True if valid E.164 format, False otherwise
        """
        if not phone:
            return False
        return bool(InputValidator.PHONE_E164_PATTERN.match(phone))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if valid URL, False otherwise
        """
        if not url:
            return False
        return bool(InputValidator.URL_PATTERN.match(url))
    
    @staticmethod
    def validate_hex_color(color: str) -> bool:
        """
        Validate hex color format.
        
        Args:
            color: Hex color code to validate (e.g., #FF5733)
            
        Returns:
            bool: True if valid hex color, False otherwise
        """
        if not color:
            return False
        return bool(InputValidator.HEX_COLOR_PATTERN.match(color))
    
    @staticmethod
    def normalize_phone_e164(phone: str) -> str:
        """
        Normalize phone number to E.164 format.
        
        Args:
            phone: Phone number to normalize
            
        Returns:
            str: Normalized phone number
        """
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Ensure it starts with +
        if not cleaned.startswith('+'):
            cleaned = f'+{cleaned}'
        
        return cleaned
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize URL by ensuring it has a protocol.
        
        Args:
            url: URL to normalize
            
        Returns:
            str: Normalized URL
        """
        url = url.strip()
        
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        return url.rstrip('/')
