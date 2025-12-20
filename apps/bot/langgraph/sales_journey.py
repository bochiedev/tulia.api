"""
Sales Journey subgraph implementation for LangGraph orchestration.

This module implements the complete sales journey workflow from product discovery
to order creation and payment initiation, following the exact flow specified
in the design document.
"""
import logging
from typing import Dict, Any, Optional, List
import json

from apps.bot.langgraph.nodes import LLMNode, ToolNode
from apps.bot.conversation_state import ConversationState
from apps.bot.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class SalesNarrowQueryNode(LLMNode):
    """
    Sales narrow query LLM node for catalog search or clarification.
    
    Determines whether to search the catalog directly or ask clarifying questions
    to narrow down the customer's product requirements.
    """
    
    def __init__(self):
        """Initialize sales narrow query node."""
        system_prompt = """You are a sales assistant helping customers find products.

Your role is to analyze customer requests and decide whether to:
1. Search the catalog directly with a specific query
2. Ask a clarifying question to better understand their needs

DECISION RULES:
- If the customer's request is specific enough (mentions product names, categories, or clear features), search directly
- If the request is vague ("show me products", "what do you have"), ask ONE clarifying question
- If they're browsing generally, suggest popular categories or ask about their specific needs
- Always aim to get to a catalog search quickly - don't over-clarify

SEARCH QUERY GUIDELINES:
- Extract key product terms, categories, features, or specifications
- Include price ranges if mentioned
- Consider synonyms and related terms
- Keep queries focused and searchable

CLARIFICATION GUIDELINES:
- Ask ONE specific question to narrow down their needs
- Offer 2-3 specific options when possible
- Focus on the most important distinguishing factors (category, price range, use case)
- Keep questions conversational and helpful

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "action": "search|clarify",
    "search_query": "search terms for catalog (if action=search)",
    "search_filters": {
        "category": "category name (optional)",
        "min_price": number (optional),
        "max_price": number (optional)
    },
    "clarification_question": "question to ask customer (if action=clarify)",
    "reasoning": "brief explanation of decision"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "clarify"]},
                "search_query": {"type": "string"},
                "search_filters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "min_price": {"type": "number"},
                        "max_price": {"type": "number"}
                    }
                },
                "clarification_question": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["action", "reasoning"]
        }
        
        super().__init__("sales_narrow_query", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for sales narrow query analysis.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Turn count: {state.turn_count}"
        ]
        
        # Add conversation history context
        if state.turn_count > 1:
            if state.last_catalog_query:
                context_parts.append(f"Previous search: {state.last_catalog_query}")
            if state.last_catalog_results:
                context_parts.append(f"Previous results count: {len(state.last_catalog_results)}")
        
        # Add any selected items context
        if state.selected_item_ids:
            context_parts.append(f"Items already selected: {len(state.selected_item_ids)}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for sales narrow query analysis.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Sales narrow query result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to heuristic analysis
                return self._analyze_query_heuristic(state.incoming_message or "")
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('sales_query_analysis')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=200,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'sales_query_analysis', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["action", "reasoning"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate action
                if result["action"] not in ["search", "clarify"]:
                    result["action"] = "clarify"
                    result["reasoning"] = "Invalid action from LLM"
                
                # Ensure required fields for each action
                if result["action"] == "search" and not result.get("search_query"):
                    result["search_query"] = state.incoming_message or "products"
                
                if result["action"] == "clarify" and not result.get("clarification_question"):
                    result["clarification_question"] = "What type of product are you looking for?"
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse sales narrow query LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic analysis
                return self._analyze_query_heuristic(state.incoming_message or "")
            
        except Exception as e:
            logger.error(
                f"Sales narrow query LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic analysis
            return self._analyze_query_heuristic(state.incoming_message or "")
    
    def _analyze_query_heuristic(self, message: str) -> Dict[str, Any]:
        """
        Heuristic query analysis as fallback.
        
        Args:
            message: User message
            
        Returns:
            Analysis result
        """
        if not message:
            return {
                "action": "clarify",
                "clarification_question": "What can I help you find today?",
                "reasoning": "Empty message - need clarification"
            }
        
        message_lower = message.lower().strip()
        
        # Check for specific product indicators
        specific_indicators = [
            'phone', 'laptop', 'shirt', 'shoes', 'book', 'watch', 'bag',
            'headphones', 'camera', 'tablet', 'dress', 'jacket', 'pants'
        ]
        
        # Check for vague requests
        vague_indicators = [
            'show me', 'what do you have', 'products', 'items', 'catalog',
            'browse', 'see all', 'anything', 'something'
        ]
        
        # Check for price mentions
        has_price = any(word in message_lower for word in ['cheap', 'expensive', 'under', 'below', 'above', 'ksh', '$'])
        
        # Check for category mentions
        categories = ['electronics', 'clothing', 'books', 'accessories', 'home', 'sports']
        has_category = any(cat in message_lower for cat in categories)
        
        # Decision logic
        if any(indicator in message_lower for indicator in specific_indicators) or has_price or has_category:
            # Specific enough to search
            return {
                "action": "search",
                "search_query": message,
                "search_filters": {},
                "reasoning": "Message contains specific product indicators"
            }
        elif any(indicator in message_lower for indicator in vague_indicators):
            # Too vague - need clarification
            return {
                "action": "clarify",
                "clarification_question": "What type of product are you looking for? For example, electronics, clothing, or something specific?",
                "reasoning": "Message is too vague - need clarification"
            }
        else:
            # Default to search for other cases
            return {
                "action": "search",
                "search_query": message,
                "search_filters": {},
                "reasoning": "Default to search for unclear cases"
            }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from sales narrow query result.
        
        Args:
            state: Current conversation state
            result: LLM analysis result
            
        Returns:
            Updated conversation state
        """
        action = result["action"]
        
        if action == "search":
            # Prepare for catalog search
            state.last_catalog_query = result.get("search_query", state.incoming_message)
            state.last_catalog_filters = result.get("search_filters", {})
            
            # Set next step in sales journey
            state.sales_step = "catalog_search"
            
        elif action == "clarify":
            # Prepare clarification response
            state.response_text = result.get("clarification_question", "What can I help you find?")
            
            # Set next step to wait for clarification
            state.sales_step = "awaiting_clarification"
        
        logger.info(
            f"Sales narrow query: {action}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "action": action,
                "search_query": state.last_catalog_query,
                "reasoning": result.get("reasoning", "")
            }
        )
        
        return state


class CatalogPresentOptionsNode(LLMNode):
    """
    Catalog present options LLM node with WhatsApp formatting.
    
    Formats catalog search results into WhatsApp-friendly product shortlists
    with maximum 6 items as specified in the design.
    """
    
    def __init__(self):
        """Initialize catalog present options node."""
        system_prompt = """You are a sales assistant presenting product options to customers via WhatsApp.

Your role is to format catalog search results into clear, engaging product presentations.

FORMATTING RULES:
- Maximum 6 products per response (STRICT LIMIT)
- Use numbered list format (1. 2. 3. etc.)
- Include product name, key features, and price
- Keep descriptions concise but informative
- Use WhatsApp-friendly formatting (no complex markdown)
- Include stock status if relevant
- End with a clear call-to-action

PRESENTATION GUIDELINES:
- Highlight the most relevant products first
- Include price in local currency (KES)
- Mention key differentiating features
- Use conversational, helpful tone
- If many results, mention that more options are available
- Provide clear next steps for selection

CATALOG LINK RULES:
Show catalog link when ANY is true:
- Total matches >= 50 AND user query was vague
- User asks "see all items/catalog/list everything"
- Results are low confidence (no clear top matches)
- Product selection requires visuals/variants beyond WhatsApp UX
- User rejected 2 shortlists in a row

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "presentation_text": "formatted product list with WhatsApp formatting",
    "show_catalog_link": true|false,
    "catalog_link_reason": "reason for showing catalog link (if applicable)",
    "selected_products": [
        {
            "product_id": "uuid",
            "position": 1,
            "name": "product name",
            "price": number
        }
    ],
    "total_shown": number,
    "has_more_results": true|false
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "presentation_text": {"type": "string"},
                "show_catalog_link": {"type": "boolean"},
                "catalog_link_reason": {"type": "string"},
                "selected_products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "position": {"type": "integer"},
                            "name": {"type": "string"},
                            "price": {"type": "number"}
                        },
                        "required": ["product_id", "position", "name"]
                    }
                },
                "total_shown": {"type": "integer"},
                "has_more_results": {"type": "boolean"}
            },
            "required": ["presentation_text", "show_catalog_link", "selected_products", "total_shown", "has_more_results"]
        }
        
        super().__init__("catalog_present_options", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for catalog presentation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Search query: {state.last_catalog_query}",
            f"Total matches found: {state.catalog_total_matches_estimate or 0}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Customer language: {state.response_language}"
        ]
        
        # Add search results
        if state.last_catalog_results:
            context_parts.append("Search results:")
            for i, product in enumerate(state.last_catalog_results[:6], 1):
                product_info = f"{i}. {product.get('name', 'Unknown')} - KES {product.get('price', 0)}"
                if product.get('description'):
                    product_info += f" - {product['description'][:100]}"
                if not product.get('in_stock', True):
                    product_info += " (Out of stock)"
                context_parts.append(product_info)
        else:
            context_parts.append("No search results available")
        
        # Add catalog link context
        if state.catalog_total_matches_estimate and state.catalog_total_matches_estimate >= 50:
            context_parts.append(f"Large catalog ({state.catalog_total_matches_estimate} total matches) - consider catalog link")
        
        # Add rejection history if available
        rejection_count = getattr(state, 'shortlist_rejections', 0)
        if rejection_count >= 2:
            context_parts.append(f"Customer rejected {rejection_count} previous shortlists - consider catalog link")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for catalog presentation formatting.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Catalog presentation result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to simple formatting
                return self._format_results_simple(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('catalog_presentation')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=400,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'catalog_presentation', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                required_fields = ["presentation_text", "show_catalog_link", "selected_products", "total_shown", "has_more_results"]
                if not all(key in result for key in required_fields):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate selected_products structure
                if not isinstance(result["selected_products"], list):
                    result["selected_products"] = []
                
                # Ensure total_shown matches actual products
                result["total_shown"] = len(result["selected_products"])
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse catalog presentation LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to simple formatting
                return self._format_results_simple(state)
            
        except Exception as e:
            logger.error(
                f"Catalog presentation LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to simple formatting
            return self._format_results_simple(state)
    
    def _format_results_simple(self, state: ConversationState) -> Dict[str, Any]:
        """
        Simple fallback formatting for catalog results.
        
        Args:
            state: Current conversation state
            
        Returns:
            Simple formatted result
        """
        if not state.last_catalog_results:
            return {
                "presentation_text": "I couldn't find any products matching your search. Could you try a different search term?",
                "show_catalog_link": True,
                "catalog_link_reason": "No results found",
                "selected_products": [],
                "total_shown": 0,
                "has_more_results": False
            }
        
        # Format up to 6 products
        products_to_show = state.last_catalog_results[:6]
        presentation_lines = ["Here are some products I found for you:\n"]
        
        selected_products = []
        for i, product in enumerate(products_to_show, 1):
            name = product.get('name', 'Unknown Product')
            price = product.get('price', 0)
            
            line = f"{i}. {name}"
            if price:
                line += f" - KES {price:,.0f}"
            
            if not product.get('in_stock', True):
                line += " (Out of stock)"
            
            presentation_lines.append(line)
            
            selected_products.append({
                "product_id": product.get('product_id', ''),
                "position": i,
                "name": name,
                "price": price
            })
        
        presentation_lines.append("\nWhich one interests you? Just reply with the number.")
        
        # Check if catalog link should be shown
        total_matches = state.catalog_total_matches_estimate or 0
        show_catalog_link = total_matches >= 50 or len(products_to_show) < 3
        
        return {
            "presentation_text": "\n".join(presentation_lines),
            "show_catalog_link": show_catalog_link,
            "catalog_link_reason": "Large catalog or few results" if show_catalog_link else "",
            "selected_products": selected_products,
            "total_shown": len(selected_products),
            "has_more_results": total_matches > len(products_to_show)
        }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from catalog presentation result.
        
        Args:
            state: Current conversation state
            result: LLM presentation result
            
        Returns:
            Updated conversation state
        """
        # Set response text
        presentation_text = result["presentation_text"]
        
        # Add catalog link if needed
        if result.get("show_catalog_link", False) and state.catalog_link_base:
            catalog_url = f"{state.catalog_link_base}?tenant_id={state.tenant_id}"
            if state.last_catalog_query:
                catalog_url += f"&search={state.last_catalog_query}"
            
            presentation_text += f"\n\n🌐 Or browse our full catalog: {catalog_url}"
        
        state.response_text = presentation_text
        
        # Update sales step
        state.sales_step = "awaiting_selection"
        
        # Store presented products for selection
        state.presented_products = result.get("selected_products", [])
        
        logger.info(
            f"Catalog options presented: {result['total_shown']} products",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "total_shown": result["total_shown"],
                "has_more_results": result["has_more_results"],
                "show_catalog_link": result.get("show_catalog_link", False),
                "catalog_link_reason": result.get("catalog_link_reason", "")
            }
        )
        
        return state

class ProductDisambiguateNode(LLMNode):
    """
    Product disambiguate LLM node for order preparation.
    
    Confirms item selection and gathers missing details needed for order creation.
    """
    
    def __init__(self):
        """Initialize product disambiguate node."""
        system_prompt = """You are a sales assistant helping customers finalize their product selection for ordering.

Your role is to confirm product selection and gather any missing information needed to create an order.

CONFIRMATION TASKS:
- Confirm the specific product the customer selected
- Verify quantity needed
- Check if variants/options need to be specified
- Gather delivery preferences if required
- Confirm customer is ready to proceed with order

INFORMATION GATHERING:
- Ask for quantity if not specified (default to 1)
- Ask about product variants (size, color, model) if applicable
- Collect delivery address if required for order
- Confirm any special requirements or notes

DECISION RULES:
- If all required info is available: proceed to order creation
- If missing critical info: ask for specific details needed
- Keep questions focused and efficient
- Don't over-complicate the process

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "action": "proceed|gather_info",
    "confirmed_product": {
        "product_id": "uuid",
        "name": "product name",
        "price": number,
        "quantity": number,
        "variant_selection": {}
    },
    "missing_info": ["quantity", "variant", "delivery_address"],
    "question_to_ask": "specific question for missing info (if action=gather_info)",
    "ready_for_order": true|false,
    "reasoning": "brief explanation"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["proceed", "gather_info"]},
                "confirmed_product": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                        "quantity": {"type": "integer"},
                        "variant_selection": {"type": "object"}
                    }
                },
                "missing_info": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "question_to_ask": {"type": "string"},
                "ready_for_order": {"type": "boolean"},
                "reasoning": {"type": "string"}
            },
            "required": ["action", "ready_for_order", "reasoning"]
        }
        
        super().__init__("product_disambiguate", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for product disambiguation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}"
        ]
        
        # Add selected product details if available
        if hasattr(state, 'selected_product_details') and state.selected_product_details:
            product = state.selected_product_details
            context_parts.append(f"Selected product: {product.get('name', 'Unknown')}")
            context_parts.append(f"Price: KES {product.get('price', 0)}")
            if product.get('variants'):
                context_parts.append(f"Available variants: {len(product['variants'])}")
        
        # Add current cart state
        if state.cart:
            context_parts.append(f"Current cart items: {len(state.cart)}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for product disambiguation.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Product disambiguation result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to simple disambiguation
                return self._disambiguate_simple(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('product_disambiguation')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=300,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'product_disambiguation', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["action", "ready_for_order", "reasoning"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate action
                if result["action"] not in ["proceed", "gather_info"]:
                    result["action"] = "gather_info"
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse product disambiguation LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to simple disambiguation
                return self._disambiguate_simple(state)
            
        except Exception as e:
            logger.error(
                f"Product disambiguation LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to simple disambiguation
            return self._disambiguate_simple(state)
    
    def _disambiguate_simple(self, state: ConversationState) -> Dict[str, Any]:
        """
        Simple fallback disambiguation logic.
        
        Args:
            state: Current conversation state
            
        Returns:
            Simple disambiguation result
        """
        # Check if we have selected product details
        if not hasattr(state, 'selected_product_details') or not state.selected_product_details:
            return {
                "action": "gather_info",
                "question_to_ask": "Which product would you like to order? Please let me know the specific item.",
                "ready_for_order": False,
                "reasoning": "No product selected yet"
            }
        
        product = state.selected_product_details
        
        # Check for basic requirements
        missing_info = []
        
        # Check quantity (default to 1 if not specified)
        quantity = 1
        message_lower = (state.incoming_message or "").lower()
        
        # Try to extract quantity from message
        import re
        quantity_match = re.search(r'\b(\d+)\b', message_lower)
        if quantity_match:
            quantity = int(quantity_match.group(1))
        
        # Check if product has variants that need selection
        if product.get('variants') and len(product['variants']) > 1:
            missing_info.append("variant")
        
        # If missing critical info, ask for it
        if missing_info:
            if "variant" in missing_info:
                variants_text = ", ".join([v.get('name', 'Option') for v in product['variants'][:3]])
                question = f"Which option would you like for {product['name']}? Available: {variants_text}"
            else:
                question = "How many would you like to order?"
            
            return {
                "action": "gather_info",
                "question_to_ask": question,
                "missing_info": missing_info,
                "ready_for_order": False,
                "reasoning": f"Missing info: {', '.join(missing_info)}"
            }
        
        # Ready to proceed
        return {
            "action": "proceed",
            "confirmed_product": {
                "product_id": product.get('product_id', ''),
                "name": product.get('name', ''),
                "price": product.get('price', 0),
                "quantity": quantity,
                "variant_selection": {}
            },
            "ready_for_order": True,
            "reasoning": "All required information available"
        }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from product disambiguation result.
        
        Args:
            state: Current conversation state
            result: LLM disambiguation result
            
        Returns:
            Updated conversation state
        """
        action = result["action"]
        
        if action == "gather_info":
            # Set question to ask
            state.response_text = result.get("question_to_ask", "Could you provide more details about your order?")
            state.sales_step = "gathering_order_info"
            
        elif action == "proceed" and result.get("ready_for_order", False):
            # Prepare cart for order creation
            confirmed_product = result.get("confirmed_product", {})
            
            if confirmed_product:
                # Add to cart
                cart_item = {
                    "product_id": confirmed_product.get("product_id"),
                    "quantity": confirmed_product.get("quantity", 1),
                    "variant_selection": confirmed_product.get("variant_selection", {})
                }
                
                # Initialize cart if needed
                if not state.cart:
                    state.cart = []
                
                state.cart.append(cart_item)
                state.sales_step = "ready_for_order"
        
        logger.info(
            f"Product disambiguation: {action}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "action": action,
                "ready_for_order": result.get("ready_for_order", False),
                "missing_info": result.get("missing_info", []),
                "reasoning": result.get("reasoning", "")
            }
        )
        
        return state


class SalesJourneySubgraph:
    """
    Sales Journey subgraph implementation.
    
    Orchestrates the complete sales workflow from product discovery to order creation
    following the exact flow specified in the design document.
    """
    
    def __init__(self):
        """Initialize sales journey subgraph."""
        self.logger = logging.getLogger(__name__)
    
    async def execute_sales_journey(self, state: ConversationState) -> ConversationState:
        """
        Execute the complete sales journey workflow.
        
        Implements the sales journey flow:
        1. sales_narrow_query -> clarify OR search
        2. catalog_search (if search)
        3. catalog_present_options
        4. User selection -> catalog_get_item
        5. product_disambiguate
        6. order_create (if ready)
        7. offers_get_applicable
        8. payment_get_methods
        9. payment_router_prompt
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        try:
            # Determine current step in sales journey
            current_step = getattr(state, 'sales_step', 'start')
            
            self.logger.info(
                f"Executing sales journey step: {current_step}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "sales_step": current_step,
                    "turn_count": state.turn_count
                }
            )
            
            if current_step == 'start':
                return await self._step_narrow_query(state)
            elif current_step == 'catalog_search':
                return await self._step_catalog_search(state)
            elif current_step == 'present_options':
                return await self._step_present_options(state)
            elif current_step == 'awaiting_selection':
                return await self._step_handle_selection(state)
            elif current_step == 'get_item_details':
                return await self._step_get_item_details(state)
            elif current_step == 'disambiguate_product':
                return await self._step_disambiguate_product(state)
            elif current_step == 'ready_for_order':
                return await self._step_create_order(state)
            elif current_step == 'order_created':
                return await self._step_handle_offers(state)
            elif current_step == 'offers_handled':
                return await self._step_payment_methods(state)
            elif current_step == 'payment_routing':
                return await self._step_payment_routing(state)
            else:
                # Default to narrow query for unknown steps
                return await self._step_narrow_query(state)
                
        except Exception as e:
            self.logger.error(
                f"Sales journey execution failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "sales_step": getattr(state, 'sales_step', 'unknown')
                },
                exc_info=True
            )
            
            # Set error response and escalation
            state.response_text = "I'm having trouble processing your request. Let me connect you with someone who can help."
            state.set_escalation("Sales journey execution error")
            return state
    
    async def _step_narrow_query(self, state: ConversationState) -> ConversationState:
        """Execute sales narrow query step."""
        # Create and execute narrow query node
        narrow_query_node = SalesNarrowQueryNode()
        updated_state = await narrow_query_node.execute(state)
        
        # Check if we need to search or clarify
        if getattr(updated_state, 'sales_step', '') == 'catalog_search':
            # Proceed to catalog search
            return await self._step_catalog_search(updated_state)
        else:
            # Clarification needed - response already set
            return updated_state
    
    async def _step_catalog_search(self, state: ConversationState) -> ConversationState:
        """Execute catalog search step."""
        from apps.bot.tools.registry import get_tool
        
        # Get catalog search tool
        catalog_search_tool = get_tool("catalog_search")
        if not catalog_search_tool:
            state.response_text = "I'm having trouble searching our catalog right now. Please try again."
            return state
        
        # Prepare search parameters
        search_params = {
            "tenant_id": state.tenant_id,
            "request_id": state.request_id,
            "conversation_id": state.conversation_id,
            "query": state.last_catalog_query or state.incoming_message,
            "limit": 6  # WhatsApp shortlist limit
        }
        
        # Add filters if available
        if state.last_catalog_filters:
            search_params.update(state.last_catalog_filters)
        
        # Execute search
        search_result = catalog_search_tool.execute(**search_params)
        
        if search_result.success:
            # Update state with search results
            data = search_result.data
            state.last_catalog_results = data.get("products", [])
            state.catalog_total_matches_estimate = data.get("total_matches_estimate", 0)
            
            # Proceed to present options
            state.sales_step = 'present_options'
            return await self._step_present_options(state)
        else:
            # Search failed
            state.response_text = f"I couldn't search our catalog right now: {search_result.error}. Could you try a different search?"
            return state
    
    async def _step_present_options(self, state: ConversationState) -> ConversationState:
        """Execute catalog present options step."""
        # Create and execute present options node
        present_options_node = CatalogPresentOptionsNode()
        updated_state = await present_options_node.execute(state)
        
        # Options are now presented, waiting for user selection
        return updated_state
    
    async def _step_handle_selection(self, state: ConversationState) -> ConversationState:
        """Handle user product selection."""
        message = (state.incoming_message or "").strip()
        
        # Try to parse selection number
        try:
            selection_num = int(message)
            presented_products = getattr(state, 'presented_products', [])
            
            if 1 <= selection_num <= len(presented_products):
                # Valid selection
                selected_product = presented_products[selection_num - 1]
                state.selected_item_ids = [selected_product["product_id"]]
                state.sales_step = 'get_item_details'
                return await self._step_get_item_details(state)
            else:
                state.response_text = f"Please choose a number between 1 and {len(presented_products)}."
                return state
                
        except ValueError:
            # Not a number - check for other selection patterns
            message_lower = message.lower()
            
            # Check for "see all" or catalog requests
            if any(phrase in message_lower for phrase in ["see all", "catalog", "more options", "browse"]):
                if state.catalog_link_base:
                    catalog_url = f"{state.catalog_link_base}?tenant_id={state.tenant_id}"
                    if state.last_catalog_query:
                        catalog_url += f"&search={state.last_catalog_query}"
                    state.response_text = f"Browse our full catalog here: {catalog_url}\n\nOr let me know if you'd like to search for something specific!"
                else:
                    state.response_text = "Let me search for more options. What specifically are you looking for?"
                    state.sales_step = 'start'  # Restart search process
                return state
            
            # Check for new search request
            elif any(phrase in message_lower for phrase in ["search", "find", "looking for", "want"]):
                # New search request
                state.sales_step = 'start'
                return await self._step_narrow_query(state)
            
            else:
                # Invalid selection
                presented_products = getattr(state, 'presented_products', [])
                if presented_products:
                    state.response_text = f"Please choose a number (1-{len(presented_products)}) or let me know what else you're looking for."
                else:
                    state.response_text = "What can I help you find today?"
                    state.sales_step = 'start'
                return state
    
    async def _step_get_item_details(self, state: ConversationState) -> ConversationState:
        """Get detailed product information."""
        from apps.bot.tools.registry import get_tool
        
        if not state.selected_item_ids:
            state.response_text = "Please select a product first."
            state.sales_step = 'awaiting_selection'
            return state
        
        # Get catalog get item tool
        get_item_tool = get_tool("catalog_get_item")
        if not get_item_tool:
            state.response_text = "I'm having trouble getting product details right now. Please try again."
            return state
        
        product_id = state.selected_item_ids[0]
        
        # Get product details
        item_result = get_item_tool.execute(
            tenant_id=state.tenant_id,
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            product_id=product_id
        )
        
        if item_result.success:
            # Store product details
            state.selected_product_details = item_result.data
            state.sales_step = 'disambiguate_product'
            return await self._step_disambiguate_product(state)
        else:
            state.response_text = f"I couldn't get details for that product: {item_result.error}. Please try selecting another one."
            state.sales_step = 'awaiting_selection'
            return state
    
    async def _step_disambiguate_product(self, state: ConversationState) -> ConversationState:
        """Execute product disambiguation step."""
        # Create and execute disambiguate node
        disambiguate_node = ProductDisambiguateNode()
        updated_state = await disambiguate_node.execute(state)
        
        # Check if ready for order or need more info
        if getattr(updated_state, 'sales_step', '') == 'ready_for_order':
            return await self._step_create_order(updated_state)
        else:
            # More info needed - response already set
            return updated_state
    
    async def _step_create_order(self, state: ConversationState) -> ConversationState:
        """Create order from cart items."""
        from apps.bot.tools.registry import get_tool
        
        if not state.cart or not state.customer_id:
            state.response_text = "I need to set up your order first. Let me help you with that."
            state.sales_step = 'disambiguate_product'
            return state
        
        # Get order create tool
        order_create_tool = get_tool("order_create")
        if not order_create_tool:
            state.response_text = "I'm having trouble creating your order right now. Please try again."
            return state
        
        # Create order
        order_result = order_create_tool.execute(
            tenant_id=state.tenant_id,
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            customer_id=state.customer_id,
            items=state.cart
        )
        
        if order_result.success:
            # Update state with order details
            order_data = order_result.data
            state.order_id = order_data["order_id"]
            state.order_totals = {
                "subtotal": order_data["subtotal"],
                "tax": order_data["tax"],
                "total": order_data["total"],
                "currency": order_data["currency"]
            }
            
            # Generate order confirmation message
            items_text = []
            for item in order_data["items"]:
                items_text.append(f"• {item['name']} (Qty: {item['quantity']}) - KES {item['line_total']:,.0f}")
            
            confirmation_text = f"""✅ Order created successfully!

Order #{order_data['order_reference']}

Items:
{chr(10).join(items_text)}

Subtotal: KES {order_data['subtotal']:,.0f}
Tax: KES {order_data['tax']:,.0f}
Total: KES {order_data['total']:,.0f}

Let me check for any available offers and payment options..."""
            
            state.response_text = confirmation_text
            state.sales_step = 'order_created'
            return await self._step_handle_offers(state)
        else:
            state.response_text = f"I couldn't create your order: {order_result.error}. Please try again or let me know if you need help."
            return state
    
    async def _step_handle_offers(self, state: ConversationState) -> ConversationState:
        """Handle offers and coupons."""
        from apps.bot.tools.registry import get_tool
        
        if not state.order_id:
            state.response_text = "I need to create your order first."
            state.sales_step = 'ready_for_order'
            return state
        
        # Get offers tool
        offers_tool = get_tool("offers_get_applicable")
        if not offers_tool:
            # Skip offers if tool not available
            state.sales_step = 'offers_handled'
            return await self._step_payment_methods(state)
        
        # Get applicable offers
        offers_result = offers_tool.execute(
            tenant_id=state.tenant_id,
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            order_id=state.order_id
        )
        
        if offers_result.success and offers_result.data.get("offers"):
            # Present available offers
            offers = offers_result.data["offers"]
            offers_text = []
            
            for offer in offers[:3]:  # Limit to 3 offers
                discount_text = f"{offer.get('discount_percent', 0)}%" if offer.get('discount_percent') else f"KES {offer.get('discount_amount', 0)}"
                offers_text.append(f"• {offer.get('name', 'Special Offer')} - {discount_text} off")
            
            if offers_text:
                state.response_text += f"\n\n🎉 Available offers:\n{chr(10).join(offers_text)}\n\nWould you like to apply any of these offers? Or shall we proceed to payment?"
                state.available_offers = offers
                # Stay in offers_handled step to wait for user response
                state.sales_step = 'offers_handled'
                return state
        
        # No offers or offers failed - proceed to payment
        state.sales_step = 'offers_handled'
        return await self._step_payment_methods(state)
    
    async def _step_payment_methods(self, state: ConversationState) -> ConversationState:
        """Get available payment methods."""
        from apps.bot.tools.registry import get_tool
        
        # Get payment methods tool
        payment_methods_tool = get_tool("payment_get_methods")
        if not payment_methods_tool:
            state.response_text = "I'm having trouble getting payment options right now. Please try again."
            return state
        
        # Get payment methods
        methods_result = payment_methods_tool.execute(
            tenant_id=state.tenant_id,
            request_id=state.request_id,
            conversation_id=state.conversation_id
        )
        
        if methods_result.success:
            # Store payment methods
            state.available_payment_methods = methods_result.data.get("methods", [])
            state.sales_step = 'payment_routing'
            return await self._step_payment_routing(state)
        else:
            state.response_text = f"I couldn't get payment options: {methods_result.error}. Please try again."
            return state
    
    async def _step_payment_routing(self, state: ConversationState) -> ConversationState:
        """Route to appropriate payment method."""
        if not state.available_payment_methods:
            state.response_text = "No payment methods are available right now. Please contact support for assistance."
            state.set_escalation("No payment methods available")
            return state
        
        # Present payment options
        methods_text = []
        for i, method in enumerate(state.available_payment_methods, 1):
            method_name = method.get('name', 'Payment Method')
            methods_text.append(f"{i}. {method_name}")
        
        total = state.order_totals.get('total', 0)
        currency = state.order_totals.get('currency', 'KES')
        
        payment_text = f"""💳 Choose your payment method:

{chr(10).join(methods_text)}

Total to pay: {currency} {total:,.0f}

Reply with the number of your preferred payment method."""
        
        state.response_text = payment_text
        
        # Sales journey complete - payment selection will be handled by payment journey
        state.journey = "payment"  # Transition to payment journey
        
        return state


# Sales journey entry function for LangGraph integration
async def execute_sales_journey_node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point for sales journey execution in LangGraph.
    
    Args:
        state_dict: LangGraph state dictionary
        
    Returns:
        Updated state dictionary
    """
    # Convert dict to ConversationState
    conv_state = ConversationState.from_dict(state_dict)
    
    # Execute sales journey
    sales_journey = SalesJourneySubgraph()
    updated_state = await sales_journey.execute_sales_journey(conv_state)
    
    # Convert back to dict
    return updated_state.to_dict()