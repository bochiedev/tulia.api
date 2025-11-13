"""
Pesapal payment service for East Africa.

Pesapal supports:
- Card payments (Visa, Mastercard)
- Mobile money (M-Pesa, Airtel Money, etc.)
- Bank transfers
- Multiple currencies (KES, UGX, TZS, USD)

Documentation: https://developer.pesapal.com/
"""
import logging
import requests
import json
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings
from django.core.cache import cache

from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class PesapalError(TuliaException):
    """Raised when Pesapal API operation fails."""
    pass


class PesapalService:
    """Service for Pesapal payment integration."""
    
    @classmethod
    def _get_access_token(cls) -> str:
        """
        Get Pesapal OAuth access token (cached).
        
        Returns:
            str: Access token
        """
        # Check cache first
        cache_key = 'pesapal_access_token'
        token = cache.get(cache_key)
        
        if token:
            return token
        
        # Generate new token
        try:
            api_url = f"{settings.PESAPAL_API_URL}/api/Auth/RequestToken"
            
            payload = {
                'consumer_key': settings.PESAPAL_CONSUMER_KEY,
                'consumer_secret': settings.PESAPAL_CONSUMER_SECRET
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            token = data['token']
            expires_in = data.get('expiryDate')  # Token expiry
            
            # Cache for 23 hours (tokens typically expire after 24 hours)
            cache.set(cache_key, token, 82800)
            
            logger.info("Pesapal access token generated")
            
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to get Pesapal access token: {str(e)}",
                exc_info=True
            )
            raise PesapalError(f"Failed to authenticate with Pesapal: {str(e)}") from e
    
    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Get API headers with authorization."""
        return {
            'Authorization': f'Bearer {cls._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def register_ipn(cls, url: str, ipn_notification_type: str = 'GET') -> Dict:
        """
        Register IPN (Instant Payment Notification) URL.
        
        Args:
            url: IPN callback URL
            ipn_notification_type: 'GET' or 'POST'
            
        Returns:
            dict: IPN registration details with ipn_id
        """
        try:
            api_url = f"{settings.PESAPAL_API_URL}/api/URLSetup/RegisterIPN"
            
            payload = {
                'url': url,
                'ipn_notification_type': ipn_notification_type
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(
                "Pesapal IPN registered",
                extra={'ipn_id': data.get('ipn_id')}
            )
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Pesapal IPN registration failed: {str(e)}",
                exc_info=True
            )
            raise PesapalError(f"Failed to register IPN: {str(e)}") from e
    
    @classmethod
    def submit_order(cls, merchant_reference: str, amount: Decimal,
                    currency: str, description: str, callback_url: str,
                    notification_id: str, billing_address: Dict,
                    customer_email: str, customer_phone: str = None) -> Dict:
        """
        Submit an order for payment.
        
        Args:
            merchant_reference: Unique order reference
            amount: Amount in major currency units
            currency: Currency code (KES, UGX, TZS, USD)
            description: Order description
            callback_url: URL to redirect after payment
            notification_id: IPN ID from register_ipn
            billing_address: Customer billing address dict
            customer_email: Customer email
            customer_phone: Customer phone (optional)
            
        Returns:
            dict: {
                'order_tracking_id': str,
                'merchant_reference': str,
                'redirect_url': str
            }
        """
        try:
            api_url = f"{settings.PESAPAL_API_URL}/api/Transactions/SubmitOrderRequest"
            
            payload = {
                'id': merchant_reference,
                'currency': currency,
                'amount': float(amount),
                'description': description,
                'callback_url': callback_url,
                'notification_id': notification_id or settings.PESAPAL_IPN_ID,
                'billing_address': {
                    'email_address': customer_email,
                    'phone_number': customer_phone,
                    'country_code': billing_address.get('country_code', 'KE'),
                    'first_name': billing_address.get('first_name', ''),
                    'middle_name': billing_address.get('middle_name', ''),
                    'last_name': billing_address.get('last_name', ''),
                    'line_1': billing_address.get('line_1', ''),
                    'line_2': billing_address.get('line_2', ''),
                    'city': billing_address.get('city', ''),
                    'state': billing_address.get('state', ''),
                    'postal_code': billing_address.get('postal_code', ''),
                    'zip_code': billing_address.get('zip_code', '')
                }
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('error'):
                raise PesapalError(
                    f"Pesapal order submission failed: {data.get('error').get('message')}",
                    details=data
                )
            
            logger.info(
                "Pesapal order submitted",
                extra={
                    'merchant_reference': merchant_reference,
                    'order_tracking_id': data.get('order_tracking_id'),
                    'amount': float(amount)
                }
            )
            
            return {
                'order_tracking_id': data.get('order_tracking_id'),
                'merchant_reference': data.get('merchant_reference'),
                'redirect_url': data.get('redirect_url')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Pesapal order submission failed: {str(e)}",
                exc_info=True
            )
            raise PesapalError(f"Failed to submit order: {str(e)}") from e
    
    @classmethod
    def get_transaction_status(cls, order_tracking_id: str) -> Dict:
        """
        Get transaction status.
        
        Args:
            order_tracking_id: Order tracking ID from submit_order
            
        Returns:
            dict: Transaction status details
        """
        try:
            api_url = f"{settings.PESAPAL_API_URL}/api/Transactions/GetTransactionStatus"
            
            params = {'orderTrackingId': order_tracking_id}
            
            response = requests.get(
                api_url,
                params=params,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(
                "Pesapal transaction status retrieved",
                extra={
                    'order_tracking_id': order_tracking_id,
                    'status': data.get('payment_status_description')
                }
            )
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Pesapal status query failed: {str(e)}",
                exc_info=True
            )
            raise PesapalError(f"Failed to get transaction status: {str(e)}") from e
    
    @classmethod
    def refund_request(cls, confirmation_code: str, amount: Decimal,
                      username: str, remarks: str = None) -> Dict:
        """
        Request a refund for a transaction.
        
        Args:
            confirmation_code: Transaction confirmation code
            amount: Refund amount
            username: Username requesting refund
            remarks: Optional refund remarks
            
        Returns:
            dict: Refund request details
        """
        try:
            api_url = f"{settings.PESAPAL_API_URL}/api/Transactions/RefundRequest"
            
            payload = {
                'confirmation_code': confirmation_code,
                'amount': float(amount),
                'username': username,
                'remarks': remarks or 'Refund requested'
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(
                "Pesapal refund requested",
                extra={
                    'confirmation_code': confirmation_code,
                    'amount': float(amount)
                }
            )
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Pesapal refund request failed: {str(e)}",
                exc_info=True
            )
            raise PesapalError(f"Failed to request refund: {str(e)}") from e
