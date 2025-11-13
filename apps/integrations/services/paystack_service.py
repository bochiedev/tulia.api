"""
Paystack payment service for African card payments.

Paystack is widely used across Africa for card payments and supports:
- Card payments (Visa, Mastercard, Verve)
- Mobile money (Ghana, Uganda, Kenya)
- Bank transfers
- USSD payments

Documentation: https://paystack.com/docs/api/
"""
import logging
import hashlib
import hmac
import requests
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings
from django.utils import timezone

from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class PaystackError(TuliaException):
    """Raised when Paystack API operation fails."""
    pass


class PaystackService:
    """Service for Paystack payment integration."""
    
    BASE_URL = "https://api.paystack.co"
    
    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Get API headers with authorization."""
        return {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def initialize_transaction(cls, email: str, amount: Decimal, 
                              currency: str, reference: str,
                              callback_url: str, metadata: Dict = None) -> Dict:
        """
        Initialize a Paystack transaction.
        
        Args:
            email: Customer email
            amount: Amount in major currency units (e.g., KES 100)
            currency: Currency code (KES, NGN, GHS, ZAR, USD)
            reference: Unique transaction reference
            callback_url: URL to redirect after payment
            metadata: Additional metadata
            
        Returns:
            dict: {
                'authorization_url': str,
                'access_code': str,
                'reference': str
            }
        """
        try:
            # Paystack expects amount in kobo/pesewas (smallest unit)
            amount_in_kobo = int(amount * 100)
            
            payload = {
                'email': email,
                'amount': amount_in_kobo,
                'currency': currency,
                'reference': reference,
                'callback_url': callback_url,
                'metadata': metadata or {}
            }
            
            response = requests.post(
                f"{cls.BASE_URL}/transaction/initialize",
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('status'):
                raise PaystackError(
                    f"Paystack initialization failed: {data.get('message')}",
                    details=data
                )
            
            result = data['data']
            
            logger.info(
                "Paystack transaction initialized",
                extra={
                    'reference': reference,
                    'amount': float(amount),
                    'currency': currency
                }
            )
            
            return {
                'authorization_url': result['authorization_url'],
                'access_code': result['access_code'],
                'reference': result['reference']
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Paystack API request failed: {str(e)}",
                exc_info=True
            )
            raise PaystackError(f"Failed to initialize Paystack transaction: {str(e)}") from e
    
    @classmethod
    def verify_transaction(cls, reference: str) -> Dict:
        """
        Verify a Paystack transaction.
        
        Args:
            reference: Transaction reference
            
        Returns:
            dict: Transaction details including status, amount, customer
        """
        try:
            response = requests.get(
                f"{cls.BASE_URL}/transaction/verify/{reference}",
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('status'):
                raise PaystackError(
                    f"Paystack verification failed: {data.get('message')}",
                    details=data
                )
            
            transaction = data['data']
            
            logger.info(
                "Paystack transaction verified",
                extra={
                    'reference': reference,
                    'status': transaction.get('status'),
                    'amount': transaction.get('amount')
                }
            )
            
            return transaction
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Paystack verification failed: {str(e)}",
                exc_info=True
            )
            raise PaystackError(f"Failed to verify Paystack transaction: {str(e)}") from e
    
    @classmethod
    def verify_webhook_signature(cls, payload: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-Paystack-Signature header value
            
        Returns:
            bool: True if signature is valid
        """
        if not settings.PAYSTACK_SECRET_KEY:
            logger.warning("Paystack secret key not configured, skipping signature verification")
            return True
        
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    @classmethod
    def create_transfer_recipient(cls, account_number: str, bank_code: str,
                                  name: str, currency: str = 'KES') -> Dict:
        """
        Create a transfer recipient for payouts.
        
        Args:
            account_number: Bank account number
            bank_code: Bank code (e.g., '063' for Access Bank Kenya)
            name: Account holder name
            currency: Currency code
            
        Returns:
            dict: Recipient details with recipient_code
        """
        try:
            payload = {
                'type': 'nuban',  # Nigerian Uniform Bank Account Number format
                'name': name,
                'account_number': account_number,
                'bank_code': bank_code,
                'currency': currency
            }
            
            response = requests.post(
                f"{cls.BASE_URL}/transferrecipient",
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('status'):
                raise PaystackError(
                    f"Failed to create recipient: {data.get('message')}",
                    details=data
                )
            
            recipient = data['data']
            
            logger.info(
                "Paystack transfer recipient created",
                extra={
                    'recipient_code': recipient.get('recipient_code'),
                    'account_number': account_number[-4:]  # Log last 4 digits only
                }
            )
            
            return recipient
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to create Paystack recipient: {str(e)}",
                exc_info=True
            )
            raise PaystackError(f"Failed to create transfer recipient: {str(e)}") from e
    
    @classmethod
    def initiate_transfer(cls, recipient_code: str, amount: Decimal,
                         currency: str, reference: str, reason: str = None) -> Dict:
        """
        Initiate a transfer to a recipient.
        
        Args:
            recipient_code: Recipient code from create_transfer_recipient
            amount: Amount in major currency units
            currency: Currency code
            reference: Unique transfer reference
            reason: Optional transfer reason
            
        Returns:
            dict: Transfer details
        """
        try:
            # Paystack expects amount in kobo/pesewas
            amount_in_kobo = int(amount * 100)
            
            payload = {
                'source': 'balance',
                'amount': amount_in_kobo,
                'currency': currency,
                'recipient': recipient_code,
                'reference': reference,
                'reason': reason or 'Withdrawal'
            }
            
            response = requests.post(
                f"{cls.BASE_URL}/transfer",
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('status'):
                raise PaystackError(
                    f"Transfer initiation failed: {data.get('message')}",
                    details=data
                )
            
            transfer = data['data']
            
            logger.info(
                "Paystack transfer initiated",
                extra={
                    'reference': reference,
                    'amount': float(amount),
                    'status': transfer.get('status')
                }
            )
            
            return transfer
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Paystack transfer failed: {str(e)}",
                exc_info=True
            )
            raise PaystackError(f"Failed to initiate transfer: {str(e)}") from e
    
    @classmethod
    def list_banks(cls, country: str = 'kenya') -> list:
        """
        List supported banks for a country.
        
        Args:
            country: Country name (kenya, nigeria, ghana, south africa)
            
        Returns:
            list: Bank details with name, code, currency
        """
        try:
            response = requests.get(
                f"{cls.BASE_URL}/bank",
                params={'country': country},
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('status'):
                raise PaystackError(
                    f"Failed to list banks: {data.get('message')}",
                    details=data
                )
            
            return data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to list Paystack banks: {str(e)}",
                exc_info=True
            )
            raise PaystackError(f"Failed to list banks: {str(e)}") from e
