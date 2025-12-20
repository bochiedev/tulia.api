"""
Sales Journey LLM nodes for LangGraph orchestration.

This module implements the core LLM nodes for the sales journey:
- sales_narrow_query: Builds catalog search or asks clarifying questions
- catalog_present_options: Creates WhatsApp-friendly product shortlists (max 6 items)
- product_disambiguate: Confirms item selection and gathers missing details
"""
import logging
from typing import Dict, Any, Optional, List
import json

from apps.bot.langgraph.nodes import LLMNode
from apps.bot.conversation_state import ConversationState
from apps.bot.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class SalesNarrowQueryNode(LLMNode):
    """
    Sales narrow query node for catalog search or clarification.
    
    Analyzes user intent and either:
    1. Builds structured catalog search query with filters
    2. Asks ONE clarifying question to narrow down search
    
    JSON output determines next action in sales flow.
    """
    
    def __init__(self):
        """Initialize sales narrow query node."""
        system_prompt = """You are a sales assistant that helps customers find products.

Your job is to analyze the customer's request and either:
1. Build a structured catalog search query with filters
2. Ask ONE clarifying question to narrow down the search

ANALYSIS GUIDELINES:

SEARCH READY indicators:
- Specific product names or categories mentioned
- Clear product attributes (color, size, brand, price range)
- Sufficient detail to perform meaningful search
- Customer says "show me", "I want", "looking for" with specifics

CLARIFICATION NEEDED indicators:
- Vague requests ("something nice", "anything good")
- Missing key details (no category, price range, or attributes)
- Ambiguous terms that could match many categories
- Customer asks "what do you have" without specifics

SEARCH QUERY BUILDING:
- Extract main search terms from customer message
- Identify category if mentioned (electronics, clothing, food, etc.)
- Extract price range if mentioned (under 1000, between 500-2000)
- Note any specific attributes (color, brand, size)

CLARIFICATION QUESTIONS:
- Ask about category if not clear ("Are you looking for electronics, clothing, or something else?")
- Ask about price range if budget sensitive ("What's your budget range?")
- Ask about specific use case ("What will you be using it for?")
- Keep questions simple and focused on ONE aspect

WHATSAPP CONSTRAINTS:
- Keep responses concise and actionable
- Use simple language
- Focus on the most important missing information

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "action": "search|clarify",
    "search_query": "search terms if action=search",
    "category": "category filter if applicable",
    "min_price": number_or_null,
    "max_price": number_or_null,
    "clarification_question": "question text if action=clarify",
    "reasoning": "brief explanation of decision"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "clarify"]},
                "search_query": {"type": ["string", "null"]},
                "category": {"type": ["string", "null"]},
                "min_price": {"type": ["number", "null"]},
                "max_price": {"type": ["number", "null"]},
                "clarification_question": {"type": ["string", "null"]},
                "reasoning": {"type": "string", "maxLength": 100}
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
            f"Conversation turn: {state.turn_count}"
        ]
        
        # Add conversation history context
        if state.turn_count > 1:
            if state.last_catalog_query:
                context_parts.append(f"Previous search: {state.last_catalog_query}")
            if state.last_catalog_results:
                context_parts.append(f"Previous results count: {len(state.last_catalog_results)}")
        
        # Add any existing cart context
        if state.cart:
            context_parts.append(f"Items in cart: {len(state.cart)}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for sales narrow query analysis with structured JSON output.
        
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
            provider_name, model_name = llm_router._select_model('sales_analysis')
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
                temperature=0.1,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'sales_analysis', response.input_tokens)
            
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
                
                # Ensure proper fields for each action
                if result["action"] == "search":
                    if not result.get("search_query"):
                        # Fallback to heuristic if no search query
                        return self._analyze_query_heuristic(state.incoming_message or "")
                elif result["action"] == "clarify":
                    if not result.get("clarification_question"):
                        result["clarification_question"] = "What are you looking for today? I can help you find the right product."
                
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
        
        Uses keyword matching to determine if search is ready or clarification needed.
        
        Args:
            message: User message
            
        Returns:
            Analysis result
        """
        if not message:
            return {
                "action": "clarify",
                "clarification_question": "What are you looking for today?",
                "reasoning": "Empty message fallback"
            }
        
        message_lower = message.lower().strip()
        
        # Check for specific product indicators
        specific_indicators = [
            'phone', 'laptop', 'shirt', 'shoes', 'book', 'watch', 'bag',
            'iphone', 'samsung', 'nike', 'adidas', 'sony', 'hp', 'dell'
        ]
        
        # Check for search-ready patterns
        search_patterns = [
            'looking for', 'want to buy', 'need a', 'show me', 'find me',
            'i want', 'searching for', 'buy', 'purchase'
        ]
        
        # Check for price mentions
        price_indicators = ['cheap', 'expensive', 'under', 'below', 'above', 'budget', 'ksh', 'shilling']
        
        has_specific_product = any(indicator in message_lower for indicator in specific_indicators)
        has_search_intent = any(pattern in message_lower for pattern in search_patterns)
        has_price_context = any(indicator in message_lower for indicator in price_indicators)
        
        # Extract basic search terms
        search_terms = []
        for indicator in specific_indicators:
            if indicator in message_lower:
                search_terms.append(indicator)
        
        # Determine action
        if has_specific_product or (has_search_intent and len(message_lower.split()) >= 2):
            # Sufficient detail for search
            return {
                "action": "search",
                "search_query": " ".join(search_terms) if search_terms else message_lower,
                "category": None,
                "min_price": None,
                "max_price": None,
                "reasoning": "Heuristic: sufficient detail for search"
            }
        else:
            # Need clarification
            if len(message_lower.split()) <= 2:
                question = "What specific product are you looking for? For example, 'phone', 'laptop', or 'shoes'?"
            elif not has_specific_product:
                question = "What category of product interests you? Electronics, clothing, books, or something else?"
            else:
                question = "Could you tell me more about what you're looking for? Any specific brand or price range?"
            
            return {
                "action": "clarify",
                "clarification_question": question,
                "reasoning": "Heuristic: need more details"
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
            
            # Build filters from result
            filters = {}
            if result.get("category"):
                filters["category"] = result["category"]
            if result.get("min_price") is not None:
                filters["min_price"] = result["min_price"]
            if result.get("max_price") is not None:
                filters["max_price"] = result["max_price"]
            
            state.last_catalog_filters = filters
            
            # Set next action for sales flow
            state.sales_step = "catalog_search"
            
        elif action == "clarify":
            # Set clarification response
            state.response_text = result.get("clarification_question", "What are you looking for today?")
            state.sales_step = "awaiting_clarification"
        
        logger.info(
            f"Sales narrow query: {action}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "action": action,
                "search_query": result.get("search_query"),
                "filters": state.last_catalog_filters if action == "search" else None,
                "reasoning": result["reasoning"]
            }
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle errors with heuristic fallback for sales narrow query.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with fallback analysis
        """
        logger.warning(
            f"Sales narrow query LLM failed, using heuristic fallback: {error}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id
            }
        )
        
        # Use heuristic analysis as fallback
        heuristic_result = self._analyze_query_heuristic(state.incoming_message or "")
        return self._update_state_from_llm_result(state, heuristic_result)


class CatalogPresentOptionsNode(LLMNode):
    """
    Catalog present options node for WhatsApp-friendly product shortlists.
    
    Creates formatted product presentations with:
    - Maximum 6 items per response (WhatsApp constraint)
    - Clear product information (name, price, availability)
    - Numbered selection format
    - Catalog link fallback when appropriate
    
    Text output for natural language generation.
    """
    
    def __init__(self):
        """Initialize catalog present options node."""
        system_prompt = """You are a sales assistant presenting product options to customers via WhatsApp.

Your job is to create clear, concise product presentations that help customers make selections.

PRESENTATION GUIDELINES:

WHATSAPP CONSTRAINTS:
- Maximum 6 products per message (NEVER exceed this)
- Keep descriptions concise (1-2 lines per product)
- Use numbered lists for easy selection
- Include key details: name, price, availability

PRODUCT INFORMATION:
- Always show product name and price
- Mention if item is in stock or out of stock
- Include brief description if helpful
- Show currency (KES) clearly

FORMATTING RULES:
- Use numbers (1, 2, 3...) for product selection
- Format prices clearly: "KES 1,500" or "1,500 KES"
- Use "✅ In Stock" or "❌ Out of Stock" indicators
- Keep each product to 2-3 lines maximum

CUSTOMER GUIDANCE:
- Ask customer to reply with number to select
- Mention they can ask for more details about any item
- If showing fewer results, mention there might be more available
- Encourage questions about specific products

TONE:
- Friendly and helpful
- Professional but conversational
- Encouraging without being pushy
- Clear and direct

EXAMPLE FORMAT:
Here are some great options for you:

1. **iPhone 13 Pro** - KES 85,000
   Latest model with excellent camera
   ✅ In Stock

2. **Samsung Galaxy S22** - KES 65,000
   Great performance and display
   ✅ In Stock

Reply with the number of the product you'd like to know more about, or ask me any questions!

Generate a natural, helpful product presentation based on the search results provided."""
        
        # No output schema - this is a text generation node
        super().__init__("catalog_present_options", system_prompt, output_schema=None)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for catalog presentation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer search: {state.last_catalog_query}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Response language: {state.response_language}"
        ]
        
        # Add search results
        if state.last_catalog_results:
            context_parts.append(f"Search results ({len(state.last_catalog_results)} found):")
            
            for i, product in enumerate(state.last_catalog_results[:6], 1):  # Max 6 items
                stock_status = "✅ In Stock" if product.get("in_stock", False) else "❌ Out of Stock"
                price_text = f"KES {product.get('price', 'N/A')}" if product.get('price') else "Price on request"
                
                product_line = f"{i}. {product.get('name', 'Unknown Product')} - {price_text} ({stock_status})"
                if product.get('description'):
                    # Truncate description to keep it concise
                    desc = product['description'][:80] + "..." if len(product['description']) > 80 else product['description']
                    product_line += f"\n   {desc}"
                
                context_parts.append(product_line)
        else:
            context_parts.append("No search results found")
        
        # Add total matches info
        if state.catalog_total_matches_estimate:
            context_parts.append(f"Total matches estimate: {state.catalog_total_matches_estimate}")
        
        # Add catalog link context if applicable
        if state.catalog_link_base and state.catalog_total_matches_estimate and state.catalog_total_matches_estimate >= 50:
            context_parts.append("Note: Large catalog available - consider offering catalog link for browsing")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> str:
        """
        Call LLM for catalog presentation with text output.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Generated presentation text
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to template-based presentation
                return self._generate_presentation_template(state)
            
            # Get provider for text generation
            provider_name, model_name = llm_router._select_model('text_generation')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make LLM call for text generation
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=400,
                temperature=0.3
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'text_generation', response.input_tokens)
            
            # Return generated text
            return response.content.strip()
            
        except Exception as e:
            logger.error(
                f"Catalog present options LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to template-based presentation
            return self._generate_presentation_template(state)
    
    def _generate_presentation_template(self, state: ConversationState) -> str:
        """
        Generate product presentation using template as fallback.
        
        Args:
            state: Current conversation state
            
        Returns:
            Template-based presentation text
        """
        if not state.last_catalog_results:
            return "I couldn't find any products matching your search. Could you try different keywords or let me know what specific type of product you're looking for?"
        
        bot_name = state.bot_name or "I"
        results = state.last_catalog_results[:6]  # Max 6 items
        
        # Build presentation
        lines = [f"Here are some great options {bot_name} found for you:\n"]
        
        for i, product in enumerate(results, 1):
            name = product.get('name', 'Unknown Product')
            price = product.get('price')
            in_stock = product.get('in_stock', False)
            
            # Format price
            if price:
                price_text = f"KES {price:,.0f}" if isinstance(price, (int, float)) else f"KES {price}"
            else:
                price_text = "Price on request"
            
            # Format stock status
            stock_text = "✅ In Stock" if in_stock else "❌ Out of Stock"
            
            # Build product line
            product_line = f"{i}. **{name}** - {price_text}\n   {stock_text}"
            
            # Add brief description if available
            if product.get('description'):
                desc = product['description'][:60] + "..." if len(product['description']) > 60 else product['description']
                product_line += f"\n   {desc}"
            
            lines.append(product_line)
        
        lines.append("\nReply with the number to select a product, or ask me for more details about any item!")
        
        # Add catalog link if many results
        if state.catalog_total_matches_estimate and state.catalog_total_matches_estimate > len(results):
            remaining = state.catalog_total_matches_estimate - len(results)
            lines.append(f"\n({remaining} more items available - let me know if you'd like to see more options)")
        
        return "\n".join(lines)
    
    def _update_state_from_llm_result(self, state: ConversationState, result: str) -> ConversationState:
        """
        Update state from catalog presentation result.
        
        Args:
            state: Current conversation state
            result: Generated presentation text
            
        Returns:
            Updated conversation state
        """
        # Set the response text
        state.response_text = result
        
        # Update sales step
        state.sales_step = "awaiting_selection"
        
        # Store selected item IDs for easy reference
        if state.last_catalog_results:
            state.selected_item_ids = [
                product.get('product_id') for product in state.last_catalog_results[:6]
                if product.get('product_id')
            ]
        
        logger.info(
            f"Catalog options presented: {len(state.last_catalog_results)} products",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "products_shown": len(state.last_catalog_results[:6]),
                "total_matches": state.catalog_total_matches_estimate,
                "response_length": len(result)
            }
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle errors with template fallback for catalog presentation.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with template-based presentation
        """
        logger.warning(
            f"Catalog present options LLM failed, using template fallback: {error}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id
            }
        )
        
        # Use template-based presentation as fallback
        template_result = self._generate_presentation_template(state)
        return self._update_state_from_llm_result(state, template_result)

class ProductDisambiguateNode(LLMNode):
    """
    Product disambiguate node for order preparation.
    
    Analyzes customer selection and either:
    1. Confirms product selection and gathers missing order details
    2. Requests additional information needed for order
    3. Handles variant selection if applicable
    
    JSON output determines next action in sales flow.
    """
    
    def __init__(self):
        """Initialize product disambiguate node."""
        system_prompt = """You are a sales assistant helping customers finalize their product selection for ordering.

Your job is to analyze the customer's selection and determine what information is needed to proceed with the order.

ANALYSIS GUIDELINES:

SELECTION TYPES:
- Number selection (1, 2, 3) - customer chose from presented options
- Product name - customer mentioned specific product
- "More details" request - customer wants additional information
- Quantity specification - customer mentioned how many they want

INFORMATION NEEDED FOR ORDER:
- Product confirmation (which specific item)
- Quantity (how many items)
- Variant selection (size, color, model if applicable)
- Any special requirements or preferences

ACTIONS TO TAKE:

READY FOR ORDER:
- Customer clearly selected product and quantity
- No variants or variants already specified
- All necessary information is available

NEED MORE INFO:
- Customer selected product but no quantity mentioned
- Product has variants (size, color) that need selection
- Selection is ambiguous (multiple possible interpretations)
- Customer asked for more details about the product

PROVIDE DETAILS:
- Customer explicitly asked for more information
- Customer seems unsure about the product
- Need to clarify product features or specifications

RESPONSE GUIDELINES:
- Be helpful and clear about what information is needed
- Suggest reasonable defaults (quantity 1 if not specified)
- Explain available variants clearly
- Confirm the selection to avoid misunderstandings

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "action": "ready_for_order|need_more_info|provide_details",
    "selected_product_id": "product_id_if_identified",
    "quantity": number_or_null,
    "variant_selection": "variant_info_if_applicable",
    "missing_info": ["list", "of", "missing", "fields"],
    "response_message": "message to customer",
    "reasoning": "brief explanation of decision"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["ready_for_order", "need_more_info", "provide_details"]},
                "selected_product_id": {"type": ["string", "null"]},
                "quantity": {"type": ["integer", "null"], "minimum": 1},
                "variant_selection": {"type": ["string", "null"]},
                "missing_info": {"type": "array", "items": {"type": "string"}},
                "response_message": {"type": "string"},
                "reasoning": {"type": "string", "maxLength": 100}
            },
            "required": ["action", "response_message", "reasoning"]
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
        
        # Add presented products context
        if state.last_catalog_results and state.selected_item_ids:
            context_parts.append("Previously presented products:")
            
            for i, product in enumerate(state.last_catalog_results[:6], 1):
                if product.get('product_id') in state.selected_item_ids:
                    name = product.get('name', 'Unknown Product')
                    price = product.get('price', 'N/A')
                    stock = "In Stock" if product.get('in_stock', False) else "Out of Stock"
                    
                    product_line = f"{i}. {name} - KES {price} ({stock})"
                    
                    # Add variant info if available
                    if product.get('variants'):
                        variants = product['variants'][:3]  # Show first 3 variants
                        variant_names = [v.get('name', 'Variant') for v in variants]
                        product_line += f" [Variants: {', '.join(variant_names)}]"
                    
                    context_parts.append(product_line)
        
        # Add current cart context
        if state.cart:
            context_parts.append(f"Current cart: {len(state.cart)} items")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for product disambiguation with structured JSON output.
        
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
                # Fallback to heuristic analysis
                return self._analyze_selection_heuristic(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('sales_analysis')
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
                max_tokens=250,
                temperature=0.1,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'sales_analysis', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["action", "response_message", "reasoning"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate action
                if result["action"] not in ["ready_for_order", "need_more_info", "provide_details"]:
                    result["action"] = "need_more_info"
                    result["reasoning"] = "Invalid action from LLM"
                
                # Ensure missing_info is a list
                if "missing_info" not in result:
                    result["missing_info"] = []
                elif not isinstance(result["missing_info"], list):
                    result["missing_info"] = []
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse product disambiguate LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic analysis
                return self._analyze_selection_heuristic(state)
            
        except Exception as e:
            logger.error(
                f"Product disambiguate LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic analysis
            return self._analyze_selection_heuristic(state)
    
    def _analyze_selection_heuristic(self, state: ConversationState) -> Dict[str, Any]:
        """
        Heuristic selection analysis as fallback.
        
        Uses pattern matching to determine customer selection and missing info.
        
        Args:
            state: Current conversation state
            
        Returns:
            Analysis result
        """
        message = (state.incoming_message or "").lower().strip()
        
        # Check for number selection (1, 2, 3, etc.)
        import re
        number_match = re.search(r'\b([1-6])\b', message)
        
        if number_match:
            # Customer selected by number
            selection_num = int(number_match.group(1))
            
            # Find corresponding product
            if (state.last_catalog_results and 
                len(state.last_catalog_results) >= selection_num and
                state.selected_item_ids and
                len(state.selected_item_ids) >= selection_num):
                
                selected_product = state.last_catalog_results[selection_num - 1]
                product_id = selected_product.get('product_id')
                
                # Check for quantity in message
                quantity_match = re.search(r'\b(\d+)\s*(pieces?|items?|units?)?\b', message)
                quantity = 1  # Default quantity
                if quantity_match:
                    potential_quantity = int(quantity_match.group(1))
                    # Only use as quantity if it's different from selection number and reasonable
                    if potential_quantity != selection_num and potential_quantity <= 100:
                        quantity = potential_quantity
                
                # Check if product has variants
                has_variants = bool(selected_product.get('variants'))
                
                if has_variants and 'variant' not in message and 'size' not in message and 'color' not in message:
                    # Need variant selection
                    return {
                        "action": "need_more_info",
                        "selected_product_id": product_id,
                        "quantity": quantity,
                        "missing_info": ["variant_selection"],
                        "response_message": f"Great choice! {selected_product.get('name')} has different options available. Which variant would you like?",
                        "reasoning": "Heuristic: product has variants, need selection"
                    }
                else:
                    # Ready for order
                    return {
                        "action": "ready_for_order",
                        "selected_product_id": product_id,
                        "quantity": quantity,
                        "missing_info": [],
                        "response_message": f"Perfect! I'll add {quantity} x {selected_product.get('name')} to your order.",
                        "reasoning": "Heuristic: clear selection with quantity"
                    }
        
        # Check for "more details" or "tell me more" requests
        detail_keywords = ['details', 'more info', 'tell me more', 'specifications', 'features']
        if any(keyword in message for keyword in detail_keywords):
            return {
                "action": "provide_details",
                "missing_info": ["product_details"],
                "response_message": "I'd be happy to provide more details! Which product would you like to know more about? Just reply with the number.",
                "reasoning": "Heuristic: customer requested more details"
            }
        
        # Default: need clarification
        return {
            "action": "need_more_info",
            "missing_info": ["product_selection"],
            "response_message": "I'd like to help you with your selection! Could you please reply with the number of the product you're interested in (1, 2, 3, etc.)?",
            "reasoning": "Heuristic: unclear selection"
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
        
        # Set response message
        state.response_text = result["response_message"]
        
        if action == "ready_for_order":
            # Prepare cart item
            product_id = result.get("selected_product_id")
            quantity = result.get("quantity", 1)
            
            if product_id:
                cart_item = {
                    "product_id": product_id,
                    "quantity": quantity
                }
                
                # Add variant if specified
                if result.get("variant_selection"):
                    cart_item["variant_selection"] = result["variant_selection"]
                
                # Add to cart (replace existing or add new)
                state.cart = [cart_item]  # For now, single item cart
                state.sales_step = "ready_for_order"
            else:
                state.sales_step = "need_product_selection"
        
        elif action == "need_more_info":
            state.sales_step = "awaiting_info"
            
            # Store what info is missing
            missing_info = result.get("missing_info", [])
            if missing_info:
                if not hasattr(state, 'metadata') or state.metadata is None:
                    state.metadata = {}
                state.metadata["missing_order_info"] = missing_info
        
        elif action == "provide_details":
            state.sales_step = "providing_details"
        
        logger.info(
            f"Product disambiguation: {action}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "action": action,
                "selected_product_id": result.get("selected_product_id"),
                "quantity": result.get("quantity"),
                "missing_info": result.get("missing_info", []),
                "reasoning": result["reasoning"]
            }
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle errors with heuristic fallback for product disambiguation.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with heuristic analysis
        """
        logger.warning(
            f"Product disambiguate LLM failed, using heuristic fallback: {error}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id
            }
        )
        
        # Use heuristic analysis as fallback
        heuristic_result = self._analyze_selection_heuristic(state)
        return self._update_state_from_llm_result(state, heuristic_result)