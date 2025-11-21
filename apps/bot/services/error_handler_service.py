"""
Error Handler Service for sales orchestration refactor.

This service provides graceful error handling and fallback mechanisms.

Design principles:
- Graceful error handling for all handlers
- Log all errors to Sentry with full context
- Provide fallback messages for different error types
- Never leave customer without a response
"""
import logging
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorHandlerService:
    """
    Service for error handling and fallbacks.
    
    Responsibilities:
    - Handle database failures gracefully
    - Handle LLM timeouts
    - Handle payment API failures
    - Handle RAG failures
    - Handle WhatsApp API failures
    - Log errors to Sentry
    - Provide appropriate fallback messages
    """
    
    def handle_database_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        language: list
    ) -> str:
        """
        Handle database failure.
        
        Args:
            error: Exception that occurred
            context: Error context
            language: Detected language(s)
            
        Returns:
            Fallback message for customer
        """
        self._log_to_sentry(
            error=error,
            error_type='database_error',
            context=context
        )
        
        messages = {
            'en': (
                "We're experiencing technical difficulties right now. "
                "Let me connect you with someone from our team who can help."
            ),
            'sw': (
                "Tunakabiliwa na matatizo ya kiufundi sasa hivi. "
                "Wacha nikuunganishe na mtu kutoka kwa timu yetu atakayeweza kusaidia."
            ),
            'sheng': (
                "Tuna issues za technical saa hizi. "
                "Wacha nikuconnect na mse wa team yetu atakusaidia."
            )
        }
        
        return self._get_message(messages, language)
    
    def handle_llm_timeout(
        self,
        context: Dict[str, Any],
        language: list
    ) -> str:
        """
        Handle LLM timeout.
        
        Args:
            context: Error context
            language: Detected language(s)
            
        Returns:
            Fallback message for customer
        """
        self._log_to_sentry(
            error=TimeoutError("LLM timeout"),
            error_type='llm_timeout',
            context=context
        )
        
        messages = {
            'en': (
                "I'm taking a bit longer to process that. "
                "Let me show you our main menu instead."
            ),
            'sw': (
                "Ninachukua muda kidogo kuchakata hiyo. "
                "Wacha nikusaidie na menyu yetu kuu badala yake."
            ),
            'sheng': (
                "Nimechukua time kidogo ku-process hiyo. "
                "Wacha nikushow menu yetu kuu instead."
            )
        }
        
        return self._get_message(messages, language)
    
    def handle_payment_api_error(
        self,
        error: Exception,
        payment_method: str,
        context: Dict[str, Any],
        language: list
    ) -> str:
        """
        Handle payment API failure.
        
        Args:
            error: Exception that occurred
            payment_method: Payment method that failed
            context: Error context
            language: Detected language(s)
            
        Returns:
            Fallback message for customer
        """
        self._log_to_sentry(
            error=error,
            error_type='payment_api_error',
            context={**context, 'payment_method': payment_method}
        )
        
        messages = {
            'en': (
                f"We're having trouble processing {payment_method} payments right now. "
                "Would you like to try a different payment method?"
            ),
            'sw': (
                f"Tunakabiliwa na matatizo ya kuchakata malipo ya {payment_method} sasa hivi. "
                "Je, ungependa kujaribu njia nyingine ya malipo?"
            ),
            'sheng': (
                f"Tuna issues na ku-process malipo ya {payment_method} saa hizi. "
                "Aje ujaribu payment method ingine?"
            )
        }
        
        return self._get_message(messages, language)
    
    def handle_rag_failure(
        self,
        error: Exception,
        question: str,
        context: Dict[str, Any],
        language: list
    ) -> str:
        """
        Handle RAG pipeline failure.
        
        Args:
            error: Exception that occurred
            question: Question that was asked
            context: Error context
            language: Detected language(s)
            
        Returns:
            Fallback message for customer
        """
        self._log_to_sentry(
            error=error,
            error_type='rag_failure',
            context={**context, 'question': question}
        )
        
        messages = {
            'en': (
                "I'm not sure about that right now. "
                "Let me connect you with someone from our team who can answer your question."
            ),
            'sw': (
                "Sina uhakika kuhusu hiyo sasa hivi. "
                "Wacha nikuunganishe na mtu kutoka kwa timu yetu atakayeweza kujibu swali lako."
            ),
            'sheng': (
                "Siko sure kuhusu hiyo saa hizi. "
                "Wacha nikuconnect na mse wa team yetu atajibu swali yako."
            )
        }
        
        return self._get_message(messages, language)
    
    def handle_whatsapp_api_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> None:
        """
        Handle WhatsApp API failure.
        
        Args:
            error: Exception that occurred
            context: Error context
        """
        self._log_to_sentry(
            error=error,
            error_type='whatsapp_api_error',
            context=context
        )
        
        # For WhatsApp errors, we can't send a message
        # Just log and potentially retry
        logger.error(
            f"WhatsApp API error: {error}",
            extra=context
        )
    
    def get_generic_error_message(
        self,
        language: list
    ) -> str:
        """
        Get generic error message.
        
        Args:
            language: Detected language(s)
            
        Returns:
            Generic error message
        """
        messages = {
            'en': (
                "Something went wrong. "
                "Let me connect you with someone from our team."
            ),
            'sw': (
                "Kuna kitu kimekwenda vibaya. "
                "Wacha nikuunganishe na mtu kutoka kwa timu yetu."
            ),
            'sheng': (
                "Kuna kitu imego wrong. "
                "Wacha nikuconnect na mse wa team yetu."
            )
        }
        
        return self._get_message(messages, language)
    
    def _get_message(
        self,
        messages: Dict[str, str],
        language: list
    ) -> str:
        """
        Get message in appropriate language.
        
        Args:
            messages: Dict with language keys
            language: Detected language(s)
            
        Returns:
            Message in appropriate language
        """
        # Determine primary language
        lang = 'en'  # Default
        if 'sw' in language:
            lang = 'sw'
        elif 'sheng' in language:
            lang = 'sheng'
        
        return messages.get(lang, messages['en'])
    
    def _log_to_sentry(
        self,
        error: Exception,
        error_type: str,
        context: Dict[str, Any]
    ) -> None:
        """
        Log error to Sentry with full context.
        
        Args:
            error: Exception that occurred
            error_type: Type of error
            context: Error context
        """
        try:
            # Try to import and use Sentry
            import sentry_sdk
            
            with sentry_sdk.push_scope() as scope:
                # Add context
                scope.set_tag('error_type', error_type)
                scope.set_context('error_context', context)
                
                # Capture exception
                sentry_sdk.capture_exception(error)
                
        except ImportError:
            # Sentry not installed, just log
            logger.error(
                f"Error ({error_type}): {error}",
                extra=context,
                exc_info=True
            )
        except Exception as e:
            # Error logging to Sentry, just log locally
            logger.error(
                f"Failed to log to Sentry: {e}. Original error ({error_type}): {error}",
                extra=context
            )


__all__ = ['ErrorHandlerService']
