"""
Catalog fallback service for product narrowing logic.

Implements the EXACT conditions for when to show catalog links as specified in the design:
- catalog_total_matches_estimate >= 50 AND user still vague after 1 clarifying question
- user asks "see all items/catalog/list everything"
- results are low confidence (no clear top 3)
- product selection requires visuals/variants beyond WhatsApp UX
- repeated loop (user rejects 2 shortlists in a row)
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from apps.bot.conversation_state import ConversationState

logger = logging.getLogger(__name__)


class CatalogFallbackService:
    """
    Service for determining when to show catalog links and generating appropriate URLs.
    
    Implements the exact catalog fallback conditions from the design document.
    """
    
    # Patterns for detecting "see all" requests
    SEE_ALL_PATTERNS = [
        r'\bsee all\b',
        r'\bshow all\b',
        r'\blist all\b',
        r'\bview all\b',
        r'\bcatalog\b',
        r'\bbrowse\b',
        r'\bmore options\b',
        r'\ball items\b',
        r'\blist everything\b',
        r'\bshow everything\b',
        r'\bfull catalog\b',
        r'\bcomplete list\b'
    ]
    
    @classmethod
    def should_show_catalog_link(
        cls,
        state: ConversationState,
        message: Optional[str] = None,
        search_results: Optional[List[Dict[str, Any]]] = None,
        clarifying_questions_asked: int = 0
    ) -> Tuple[bool, str]:
        """
        Determine if catalog link should be shown based on EXACT conditions.
        
        Args:
            state: Current conversation state
            message: Current user message (optional)
            search_results: Current search results (optional)
            clarifying_questions_asked: Number of clarifying questions asked in current flow
            
        Returns:
            Tuple of (should_show_link, reason)
        """
        # Condition 1: catalog_total_matches_estimate >= 50 AND user still vague after 1 clarifying question
        total_matches = state.catalog_total_matches_estimate or 0
        if total_matches >= 50 and clarifying_questions_asked >= 1:
            if cls._is_user_still_vague(message):
                return True, "Large catalog with vague query after clarification"
        
        # Condition 2: user asks "see all items/catalog/list everything"
        if message and cls._is_see_all_request(message):
            return True, "User requested to see all items"
        
        # Condition 3: results are low confidence (no clear top 3)
        if search_results is not None and cls._are_results_low_confidence(search_results):
            return True, "Low confidence search results"
        
        # Condition 4: product selection requires visuals/variants beyond WhatsApp UX
        if search_results and cls._requires_visual_selection(search_results):
            return True, "Products require visual selection"
        
        # Condition 5: repeated loop (user rejects 2 shortlists in a row)
        if state.shortlist_rejections >= 2:
            return True, "User rejected multiple shortlists"
        
        return False, ""
    
    @classmethod
    def _is_user_still_vague(cls, message: Optional[str]) -> bool:
        """
        Check if user message is still vague after clarification.
        
        Args:
            message: User message to analyze
            
        Returns:
            True if message is still vague
        """
        if not message:
            return True
        
        message_lower = message.lower().strip()
        
        # Very short responses are likely vague
        if len(message_lower) < 10:
            return True
        
        # Generic responses
        vague_patterns = [
            r'\banything\b',
            r'\bwhatever\b',
            r'\bdon\'?t know\b',
            r'\bnot sure\b',
            r'\bmaybe\b',
            r'\bsomething\b',
            r'\bgood\b',
            r'\bnice\b',
            r'\bbest\b',
            r'\bcheap\b',
            r'\bexpensive\b',
            r'\bshow me\b',
            r'\bwhat do you have\b',
            r'\bwhat\'?s available\b'
        ]
        
        for pattern in vague_patterns:
            if re.search(pattern, message_lower):
                return True
        
        return False
    
    @classmethod
    def _is_see_all_request(cls, message: str) -> bool:
        """
        Check if message is a "see all" request.
        
        Args:
            message: User message to analyze
            
        Returns:
            True if message requests to see all items
        """
        message_lower = message.lower()
        
        for pattern in cls.SEE_ALL_PATTERNS:
            if re.search(pattern, message_lower):
                return True
        
        return False
    
    @classmethod
    def _are_results_low_confidence(cls, results: List[Dict[str, Any]]) -> bool:
        """
        Check if search results are low confidence (no clear top 3).
        
        Args:
            results: Search results to analyze
            
        Returns:
            True if results are low confidence
        """
        if len(results) < 3:
            return True
        
        # Check if results have confidence scores
        scored_results = [r for r in results if 'confidence' in r or 'score' in r]
        if not scored_results:
            # No confidence scores available, assume low confidence if many results
            return len(results) > 10
        
        # Check if top 3 results have significantly different scores
        top_3 = scored_results[:3]
        scores = []
        for result in top_3:
            score = result.get('confidence', result.get('score', 0))
            scores.append(float(score) if score is not None else 0)
        
        if not scores:
            return True
        
        # If highest score is low or scores are very close, consider low confidence
        max_score = max(scores)
        min_score = min(scores)
        
        # Low confidence if max score < 0.7 or score range < 0.1
        return max_score < 0.7 or (max_score - min_score) < 0.1
    
    @classmethod
    def _requires_visual_selection(cls, results: List[Dict[str, Any]]) -> bool:
        """
        Check if products require visual selection beyond WhatsApp UX.
        
        Args:
            results: Search results to analyze
            
        Returns:
            True if products need visual selection
        """
        # Check for products with many variants or visual attributes
        for result in results:
            # Check for color variants
            if 'variants' in result:
                variants = result['variants']
                if isinstance(variants, list) and len(variants) > 3:
                    return True
                
                # Check for color/visual variants
                for variant in variants:
                    if isinstance(variant, dict):
                        variant_keys = variant.keys()
                        visual_attributes = ['color', 'colour', 'style', 'design', 'pattern']
                        if any(attr in str(variant_keys).lower() for attr in visual_attributes):
                            return True
            
            # Check for image-heavy categories
            category = result.get('category', '').lower()
            visual_categories = [
                'clothing', 'fashion', 'shoes', 'jewelry', 'accessories',
                'furniture', 'home decor', 'art', 'crafts'
            ]
            if any(cat in category for cat in visual_categories):
                return True
        
        return False
    
    @classmethod
    def generate_catalog_url(
        cls,
        state: ConversationState,
        selected_product_id: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate catalog URL with deep-linking capability.
        
        Args:
            state: Current conversation state
            selected_product_id: Optional product ID for deep-linking
            search_query: Optional search query to include
            
        Returns:
            Generated catalog URL or None if no base URL configured
        """
        if not state.catalog_link_base:
            return None
        
        # Start with base URL and tenant ID
        url = f"{state.catalog_link_base}?tenant_id={state.tenant_id}"
        
        # Add product ID for deep-linking
        if selected_product_id:
            url += f"&product_id={selected_product_id}"
        
        # Add search query
        search_to_use = search_query or state.last_catalog_query
        if search_to_use:
            # URL encode the search query
            import urllib.parse
            encoded_query = urllib.parse.quote(search_to_use)
            url += f"&search={encoded_query}"
        
        # Add conversation context for return handling
        url += f"&conversation_id={state.conversation_id}"
        url += f"&return_context=whatsapp"
        
        return url
    
    @classmethod
    def handle_catalog_return(
        cls,
        state: ConversationState,
        selected_product_id: str,
        return_message: Optional[str] = None
    ) -> ConversationState:
        """
        Handle customer return from web catalog with selected product.
        
        Args:
            state: Current conversation state
            selected_product_id: Product ID selected from catalog
            return_message: Optional return message from catalog
            
        Returns:
            Updated conversation state
        """
        # Set selected product
        state.selected_item_ids = [selected_product_id]
        
        # Update sales step to get item details
        state.sales_step = 'get_item_details'
        
        # Clear shortlist rejections since user made a selection
        state.shortlist_rejections = 0
        
        # Add metadata about catalog return
        if 'catalog_return' not in state.metadata:
            state.metadata['catalog_return'] = {}
        
        state.metadata['catalog_return'] = {
            'product_id': selected_product_id,
            'return_message': return_message,
            'timestamp': str(state.turn_count)
        }
        
        logger.info(
            f"Customer returned from catalog with product selection",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "selected_product_id": selected_product_id,
                "return_message": return_message
            }
        )
        
        return state
    
    @classmethod
    def increment_shortlist_rejection(cls, state: ConversationState) -> ConversationState:
        """
        Increment shortlist rejection counter.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        state.shortlist_rejections += 1
        
        logger.info(
            f"Shortlist rejection count incremented to {state.shortlist_rejections}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "rejection_count": state.shortlist_rejections
            }
        )
        
        return state
    
    @classmethod
    def reset_shortlist_rejections(cls, state: ConversationState) -> ConversationState:
        """
        Reset shortlist rejection counter (e.g., when user makes a selection).
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        if state.shortlist_rejections > 0:
            logger.info(
                f"Resetting shortlist rejection count from {state.shortlist_rejections}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "previous_count": state.shortlist_rejections
                }
            )
            state.shortlist_rejections = 0
        
        return state
    
    @classmethod
    def format_catalog_link_message(
        cls,
        catalog_url: str,
        reason: str,
        context: Optional[str] = None
    ) -> str:
        """
        Format catalog link message for WhatsApp.
        
        Args:
            catalog_url: Generated catalog URL
            reason: Reason for showing catalog link
            context: Optional context message
            
        Returns:
            Formatted message with catalog link
        """
        messages = {
            "Large catalog with vague query after clarification": 
                "I have many options that might interest you! For the best browsing experience:",
            "User requested to see all items": 
                "Here's our complete catalog for you to browse:",
            "Low confidence search results": 
                "I found several options, but you might prefer to browse visually:",
            "Products require visual selection": 
                "These products are best viewed with images. Check out our catalog:",
            "User rejected multiple shortlists": 
                "Let me show you our full catalog so you can browse at your own pace:"
        }
        
        intro = messages.get(reason, "Browse our full catalog:")
        
        message = f"{intro}\n\n🌐 {catalog_url}"
        
        if context:
            message += f"\n\n{context}"
        else:
            message += "\n\nOnce you find something you like, just let me know and I'll help you with the details!"
        
        return message