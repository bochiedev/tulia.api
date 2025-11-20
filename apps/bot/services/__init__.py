"""
Bot services for intent classification and handling.
"""
# Legacy intent service imports - commented out as files don't exist
# from .intent_service import IntentService, create_intent_service
# from .product_handlers import ProductIntentHandler, create_product_handler
# from .service_handlers import ServiceIntentHandler, create_service_handler
# from .consent_handlers import ConsentIntentHandler, create_consent_handler
from .handoff_handler import HandoffHandler, create_handoff_handler
from .agent_config_service import AgentConfigurationService, create_agent_config_service
from .knowledge_base_service import KnowledgeBaseService, create_knowledge_base_service
from .context_builder_service import ContextBuilderService, create_context_builder_service
from .conversation_summary_service import ConversationSummaryService, create_conversation_summary_service
from .ai_agent_service import AIAgentService, create_ai_agent_service, AgentResponse
from .fuzzy_matcher_service import FuzzyMatcherService, create_fuzzy_matcher_service
from .reference_context_manager import ReferenceContextManager
from .language_consistency_manager import LanguageConsistencyManager
from .rich_message_builder import (
    RichMessageBuilder,
    WhatsAppMessage,
    RichMessageValidationError,
    WhatsAppMessageLimits
)
from .grounded_response_validator import (
    GroundedResponseValidator,
    create_grounded_response_validator
)

__all__ = [
    # Legacy intent service exports - commented out
    # 'IntentService',
    # 'create_intent_service',
    # 'ProductIntentHandler',
    # 'create_product_handler',
    # 'ServiceIntentHandler',
    # 'create_service_handler',
    # 'ConsentIntentHandler',
    # 'create_consent_handler',
    'HandoffHandler',
    'create_handoff_handler',
    'AgentConfigurationService',
    'create_agent_config_service',
    'KnowledgeBaseService',
    'create_knowledge_base_service',
    'ContextBuilderService',
    'create_context_builder_service',
    'ConversationSummaryService',
    'create_conversation_summary_service',
    'AIAgentService',
    'create_ai_agent_service',
    'AgentResponse',
    'FuzzyMatcherService',
    'create_fuzzy_matcher_service',
    'ReferenceContextManager',
    'LanguageConsistencyManager',
    'RichMessageBuilder',
    'WhatsAppMessage',
    'RichMessageValidationError',
    'WhatsAppMessageLimits',
    'GroundedResponseValidator',
    'create_grounded_response_validator',
]
