"""
M-Pesa payment service for Kenya mobile money.

Supports:
- C2B (Customer to Business) - STK Push for customer payments
- B2B (Business to Business) - For business payments
- B2C (Business to Customer) - For tenant withdrawals to M-Pesa
- Account balance queries

Documentation: https://developer.safaricom.co.ke/APIs
"""
import logging
import base64
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings
from django.core.cache import cache

from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class MpesaError(TuliaException):
    """Raised when M-Pesa API operation fails."""
    pass


class MpesaService:
    """Service for M-Pesa mobile money integration."""
    
    @classmethod
    def _get_access_token(cls) -> str:
        """
        Get M-Pesa OAuth access token (cached for 1 hour).
        
        Returns:
            str: Access token
        """
        # Check cache first
        cache_key = 'mpesa_access_token'
        token = cache.get(cache_key)
        
        if token:
            return token
        
        # Generate new token
        try:
            api_url = f"{settings.MPESA_API_URL}/oauth/v1/generate?grant_type=client_credentials"
            
            auth_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
            auth_bytes = base64.b64encode(auth_string.encode('utf-8'))
            
            headers = {
                'Authorization': f'Basic {auth_bytes.decode("utf-8")}'
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            token = data['access_token']
            
            # Cache for 55 minutes (tokens expire after 1 hour)
            cache.set(cache_key, token, 3300)
            
            logger.info("M-Pesa access token generated")
            
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to get M-Pesa access token: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to authenticate with M-Pesa: {str(e)}") from e
    
    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Get API headers with authorization."""
        return {
            'Authorization': f'Bearer {cls._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def _generate_password(cls) -> tuple:
        """
        Generate STK Push password and timestamp.
        
        Returns:
            tuple: (password, timestamp)
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(data_to_encode.encode('utf-8')).decode('utf-8')
        return password, timestamp
    
    @classmethod
    def stk_push(cls, phone_number: str, amount: Decimal, 
                 account_reference: str, transaction_desc: str,
                 callback_url: str) -> Dict:
        """
        Initiate STK Push (Lipa Na M-Pesa Online) for customer payment.
        
        Args:
            phone_number: Customer phone number (254XXXXXXXXX format)
            amount: Amount in KES (minimum 1)
            account_reference: Reference for the transaction (max 12 chars)
            transaction_desc: Description (max 13 chars)
            callback_url: URL to receive payment result
            
        Returns:
            dict: {
                'merchant_request_id': str,
                'checkout_request_id': str,
                'response_code': str,
                'response_description': str,
                'customer_message': str
            }
        """
        try:
            # Clean phone number
            phone_number = phone_number.replace('+', '').replace(' ', '')
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            
            # Generate password and timestamp
            password, timestamp = cls._generate_password()
            
            # Prepare payload
            payload = {
                'BusinessShortCode': settings.MPESA_SHORTCODE,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),  # M-Pesa expects integer
                'PartyA': phone_number,
                'PartyB': settings.MPESA_SHORTCODE,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': account_reference[:12],  # Max 12 chars
                'TransactionDesc': transaction_desc[:13]  # Max 13 chars
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/stkpush/v1/processrequest"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check response code
            if data.get('ResponseCode') != '0':
                raise MpesaError(
                    f"STK Push failed: {data.get('ResponseDescription')}",
                    details=data
                )
            
            logger.info(
                "M-Pesa STK Push initiated",
                extra={
                    'phone': phone_number[-4:],  # Log last 4 digits only
                    'amount': float(amount),
                    'checkout_request_id': data.get('CheckoutRequestID')
                }
            )
            
            return {
                'merchant_request_id': data.get('MerchantRequestID'),
                'checkout_request_id': data.get('CheckoutRequestID'),
                'response_code': data.get('ResponseCode'),
                'response_description': data.get('ResponseDescription'),
                'customer_message': data.get('CustomerMessage')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa STK Push request failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to initiate STK Push: {str(e)}") from e
    
    @classmethod
    def query_stk_status(cls, checkout_request_id: str) -> Dict:
        """
        Query the status of an STK Push transaction.
        
        Args:
            checkout_request_id: CheckoutRequestID from stk_push
            
        Returns:
            dict: Transaction status details
        """
        try:
            password, timestamp = cls._generate_password()
            
            payload = {
                'BusinessShortCode': settings.MPESA_SHORTCODE,
                'Password': password,
                'Timestamp': timestamp,
                'CheckoutRequestID': checkout_request_id
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/stkpushquery/v1/query"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(
                "M-Pesa STK status queried",
                extra={
                    'checkout_request_id': checkout_request_id,
                    'result_code': data.get('ResultCode')
                }
            )
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa STK query failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to query STK status: {str(e)}") from e
    
    @classmethod
    def b2c_payment(cls, phone_number: str, amount: Decimal,
                   occasion: str, remarks: str, command_id: str = 'BusinessPayment') -> Dict:
        """
        Initiate B2C payment (Business to Customer) for tenant withdrawals.
        
        Args:
            phone_number: Recipient phone number (254XXXXXXXXX format)
            amount: Amount in KES
            occasion: Occasion/reason for payment
            remarks: Additional remarks
            command_id: 'BusinessPayment', 'SalaryPayment', or 'PromotionPayment'
            
        Returns:
            dict: Transaction details
        """
        try:
            # Clean phone number
            phone_number = phone_number.replace('+', '').replace(' ', '')
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            
            payload = {
                'InitiatorName': settings.MPESA_INITIATOR_NAME,
                'SecurityCredential': settings.MPESA_B2C_SECURITY_CREDENTIAL,
                'CommandID': command_id,
                'Amount': int(amount),
                'PartyA': settings.MPESA_B2C_SHORTCODE,
                'PartyB': phone_number,
                'Remarks': remarks,
                'QueueTimeOutURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/timeout",
                'ResultURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/result",
                'Occasion': occasion
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/b2c/v1/paymentrequest"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check response code
            if data.get('ResponseCode') != '0':
                raise MpesaError(
                    f"B2C payment failed: {data.get('ResponseDescription')}",
                    details=data
                )
            
            logger.info(
                "M-Pesa B2C payment initiated",
                extra={
                    'phone': phone_number[-4:],
                    'amount': float(amount),
                    'conversation_id': data.get('ConversationID')
                }
            )
            
            return {
                'conversation_id': data.get('ConversationID'),
                'originator_conversation_id': data.get('OriginatorConversationID'),
                'response_code': data.get('ResponseCode'),
                'response_description': data.get('ResponseDescription')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa B2C payment failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to initiate B2C payment: {str(e)}") from e
    
    @classmethod
    def b2b_payment(cls, receiver_shortcode: str, amount: Decimal,
                   account_reference: str, remarks: str,
                   command_id: str = 'BusinessPayBill') -> Dict:
        """
        Initiate B2B payment (Business to Business) for till payments.
        
        Args:
            receiver_shortcode: Recipient business shortcode or till number
            amount: Amount in KES
            account_reference: Account reference
            remarks: Payment remarks
            command_id: 'BusinessPayBill' or 'BusinessBuyGoods'
            
        Returns:
            dict: Transaction details
        """
        try:
            payload = {
                'Initiator': settings.MPESA_INITIATOR_NAME,
                'SecurityCredential': settings.MPESA_B2C_SECURITY_CREDENTIAL,
                'CommandID': command_id,
                'SenderIdentifierType': '4',  # 4 = Organization shortcode
                'RecieverIdentifierType': '4' if command_id == 'BusinessPayBill' else '2',  # 2 = Till number
                'Amount': int(amount),
                'PartyA': settings.MPESA_SHORTCODE,
                'PartyB': receiver_shortcode,
                'AccountReference': account_reference,
                'Remarks': remarks,
                'QueueTimeOutURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/timeout",
                'ResultURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/result"
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/b2b/v1/paymentrequest"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('ResponseCode') != '0':
                raise MpesaError(
                    f"B2B payment failed: {data.get('ResponseDescription')}",
                    details=data
                )
            
            logger.info(
                "M-Pesa B2B payment initiated",
                extra={
                    'receiver': receiver_shortcode,
                    'amount': float(amount),
                    'conversation_id': data.get('ConversationID')
                }
            )
            
            return {
                'conversation_id': data.get('ConversationID'),
                'originator_conversation_id': data.get('OriginatorConversationID'),
                'response_code': data.get('ResponseCode'),
                'response_description': data.get('ResponseDescription')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa B2B payment failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to initiate B2B payment: {str(e)}") from e
    
    @classmethod
    def c2b_register_urls(cls, confirmation_url: str, validation_url: str) -> Dict:
        """
        Register C2B validation and confirmation URLs.
        
        Args:
            confirmation_url: URL to receive payment confirmations
            validation_url: URL to validate payments before processing
            
        Returns:
            dict: Registration response
        """
        try:
            payload = {
                'ShortCode': settings.MPESA_SHORTCODE,
                'ResponseType': 'Completed',  # or 'Cancelled'
                'ConfirmationURL': confirmation_url,
                'ValidationURL': validation_url
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/c2b/v1/registerurl"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info("M-Pesa C2B URLs registered successfully")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa C2B URL registration failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to register C2B URLs: {str(e)}") from e
    
    @classmethod
    def account_balance(cls) -> Dict:
        """
        Query M-Pesa account balance.
        
        Returns:
            dict: Balance details
        """
        try:
            payload = {
                'Initiator': settings.MPESA_INITIATOR_NAME,
                'SecurityCredential': settings.MPESA_B2C_SECURITY_CREDENTIAL,
                'CommandID': 'AccountBalance',
                'PartyA': settings.MPESA_SHORTCODE,
                'IdentifierType': '4',  # 4 = Organization shortcode
                'Remarks': 'Balance query',
                'QueueTimeOutURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/timeout",
                'ResultURL': f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/result"
            }
            
            api_url = f"{settings.MPESA_API_URL}/mpesa/accountbalance/v1/query"
            
            response = requests.post(
                api_url,
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            logger.info("M-Pesa account balance queried")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"M-Pesa balance query failed: {str(e)}",
                exc_info=True
            )
            raise MpesaError(f"Failed to query account balance: {str(e)}") from e
