"""
Discovery service for intelligent catalog narrowing.
"""
import logging
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.product_intelligence import ProductIntelligenceService

logger = logging.getLogger(__name__)


class DiscoveryService:
    """
    Service for guided product/service discovery.
    
    Helps customers narrow down large catalogs through
    intelligent clarifying questions and preference extraction.
    """
    
    CLARIFICATION_THRESHOLD = 10  # Ask questions if >10 results
    
    @classmethod
    def should_ask_clarifying_questions(cls, result_count, customer_message):
        """
        Determine if clarifying questions would help.
        
        Args:
            result_count: Number of matching items
            customer_message: Customer's search/request message
        
        Returns:
            bool
        """
        # Ask if too many results
        if result_count > cls.CLARIFICATION_THRESHOLD:
            return True
        
        # Ask if query is very vague
        vague_keywords = ['something', 'anything', 'whatever', 'any', 'show me']
        if any(keyword in customer_message.lower() for keyword in vague_keywords):
            return True
        
        return False
    
    @classmethod
    def generate_clarifying_questions(cls, tenant, catalog_type, current_results, customer_message):
        """
        Generate relevant clarifying questions using LLM.
        
        Args:
            tenant: Tenant instance
            catalog_type: 'products' or 'services'
            current_results: List of current matching items
            customer_message: Customer's original message
        
        Returns:
            List of clarifying questions (2-3)
        """
        # Build context about available options
        if catalog_type == 'products':
            items_summary = cls._summarize_products(current_results)
        else:
            items_summary = cls._summarize_services(current_results)
        
        prompt = f"""
        The customer is looking for {catalog_type} and said: "{customer_message}"
        
        We found {len(current_results)} matching items:
        {items_summary}
        
        Generate 2-3 specific clarifying questions to help narrow down their choice.
        Questions should be:
        - Specific to the available options
        - Easy to answer (yes/no or simple choice)
        - Helpful for filtering results
        
        Examples:
        - "What's your budget range?"
        - "Are you looking for something for daily use or special occasions?"
        - "Do you prefer [feature A] or [feature B]?"
        
        Return only the questions, one per line.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(tenant, model_name='gpt-4o-mini')
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a helpful shopping assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            # Parse questions
            questions = [
                q.strip().lstrip('-•*').strip()
                for q in response['content'].strip().split('\n')
                if q.strip()
            ]
            
            return questions[:3]  # Max 3 questions
            
        except Exception as e:
            logger.error(f"Error generating clarifying questions: {e}")
            # Fallback questions
            if catalog_type == 'products':
                return [
                    "What's your budget range?",
                    "Are you looking for a specific brand?",
                ]
            else:
                return [
                    "When would you like to schedule this?",
                    "Is this your first time trying this service?",
                ]
    
    @classmethod
    def apply_preferences(cls, items, preferences):
        """
        Filter items based on extracted preferences.
        
        Args:
            items: List of Product or Service instances
            preferences: Dict of preferences (price_range, features, etc.)
        
        Returns:
            Filtered list of items
        """
        filtered = items
        
        # Apply price range filter
        if 'min_price' in preferences:
            filtered = [
                item for item in filtered
                if cls._get_item_price(item) >= preferences['min_price']
            ]
        
        if 'max_price' in preferences:
            filtered = [
                item for item in filtered
                if cls._get_item_price(item) <= preferences['max_price']
            ]
        
        # Apply feature filters
        if 'required_features' in preferences:
            for feature in preferences['required_features']:
                filtered = [
                    item for item in filtered
                    if cls._item_has_feature(item, feature)
                ]
        
        # Apply category filter
        if 'category' in preferences:
            filtered = [
                item for item in filtered
                if item.category and preferences['category'].lower() in item.category.name.lower()
            ]
        
        return filtered
    
    @classmethod
    def suggest_alternatives(cls, tenant, original_criteria, available_items):
        """
        Suggest alternatives when no exact matches found.
        
        Args:
            tenant: Tenant instance
            original_criteria: Customer's original search criteria
            available_items: List of available items to suggest from
        
        Returns:
            List of dicts with item and explanation
        """
        if not available_items:
            return []
        
        # Use semantic matching to find closest alternatives
        matches = ProductIntelligenceService.match_need_to_products(
            tenant,
            original_criteria,
            limit=3
        )
        
        # Generate explanations for each alternative
        alternatives = []
        for match in matches:
            try:
                explanation = cls._generate_alternative_explanation(
                    tenant,
                    match['product'],
                    original_criteria
                )
                alternatives.append({
                    'item': match['product'],
                    'score': match['score'],
                    'explanation': explanation,
                })
            except Exception as e:
                logger.error(f"Error generating alternative explanation: {e}")
        
        return alternatives
    
    @classmethod
    def extract_preferences_from_message(cls, tenant, message_text):
        """
        Extract preferences from customer message using LLM.
        
        Args:
            tenant: Tenant instance
            message_text: Customer message
        
        Returns:
            Dict of extracted preferences
        """
        prompt = f"""
        Extract shopping preferences from this customer message: "{message_text}"
        
        Extract:
        - price_range: min and max price if mentioned
        - features: list of desired features
        - category: product category if mentioned
        - use_case: intended use or occasion
        - urgency: how soon they need it
        
        Return as JSON with these fields (use null if not mentioned).
        Return ONLY valid JSON, no other text.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(tenant, model_name='gpt-4o-mini')
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a preference extraction assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            import json
            preferences = json.loads(response['content'])
            
            # Normalize price range
            if preferences.get('price_range'):
                if 'min' in preferences['price_range']:
                    preferences['min_price'] = preferences['price_range']['min']
                if 'max' in preferences['price_range']:
                    preferences['max_price'] = preferences['price_range']['max']
            
            return preferences
            
        except Exception as e:
            logger.error(f"Error extracting preferences: {e}")
            return {}
    
    @classmethod
    def _summarize_products(cls, products):
        """Summarize products for context."""
        if not products:
            return "No products"
        
        summary_lines = []
        for product in products[:10]:  # Max 10 for context
            summary_lines.append(
                f"- {product.name}: {product.price} "
                f"({product.category.name if product.category else 'Uncategorized'})"
            )
        
        if len(products) > 10:
            summary_lines.append(f"... and {len(products) - 10} more")
        
        return '\n'.join(summary_lines)
    
    @classmethod
    def _summarize_services(cls, services):
        """Summarize services for context."""
        if not services:
            return "No services"
        
        summary_lines = []
        for service in services[:10]:
            summary_lines.append(
                f"- {service.name}: {service.base_price} "
                f"({service.duration_minutes} min)"
            )
        
        if len(services) > 10:
            summary_lines.append(f"... and {len(services) - 10} more")
        
        return '\n'.join(summary_lines)
    
    @classmethod
    def _get_item_price(cls, item):
        """Get price from product or service."""
        if hasattr(item, 'price'):
            return item.price
        elif hasattr(item, 'base_price'):
            return item.base_price
        return 0
    
    @classmethod
    def _item_has_feature(cls, item, feature):
        """Check if item has a feature."""
        feature_lower = feature.lower()
        
        # Check in name and description
        if feature_lower in item.name.lower():
            return True
        if item.description and feature_lower in item.description.lower():
            return True
        
        # Check in AI analysis if available
        if hasattr(item, 'ai_analysis'):
            analysis = item.ai_analysis
            if any(feature_lower in f.lower() for f in analysis.key_features):
                return True
            if any(feature_lower in t.lower() for t in analysis.ai_tags):
                return True
        
        return False
    
    @classmethod
    def _generate_alternative_explanation(cls, tenant, product, original_criteria):
        """Generate explanation for alternative suggestion."""
        prompt = f"""
        The customer was looking for: "{original_criteria}"
        
        We're suggesting this alternative: {product.name}
        Description: {product.description}
        
        Explain briefly (1-2 sentences) why this is a good alternative,
        focusing on how it meets their needs despite not being an exact match.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(tenant, model_name='gpt-4o-mini')
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a helpful shopping assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            return response['content'].strip()
            
        except Exception as e:
            logger.error(f"Error generating alternative explanation: {e}")
            return "This is a similar option that might meet your needs."
