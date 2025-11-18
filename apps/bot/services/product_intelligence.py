"""
Product intelligence service for AI-powered recommendations.
"""
import logging
import json
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from apps.bot.models import ProductAnalysis
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ProductIntelligenceService:
    """
    Service for AI-powered product analysis and recommendations.
    
    Uses LLM to analyze products and generate intelligent
    recommendations based on customer needs.
    """
    
    CACHE_TTL_HOURS = 24
    
    @classmethod
    def analyze_product(cls, product, force_refresh=False):
        """
        Analyze product using LLM to extract characteristics.
        
        Args:
            product: Product instance
            force_refresh: Force re-analysis even if cached
        
        Returns:
            ProductAnalysis instance
        """
        # Check for existing analysis
        if not force_refresh:
            try:
                analysis = ProductAnalysis.objects.get(product=product)
                # Check if analysis is recent (within 24 hours)
                if analysis.analyzed_at > timezone.now() - timedelta(hours=cls.CACHE_TTL_HOURS):
                    return analysis
            except ProductAnalysis.DoesNotExist:
                pass
        
        # Generate analysis using LLM
        logger.info(f"Analyzing product: {product.name}")
        
        prompt = cls._build_analysis_prompt(product)
        
        try:
            provider = LLMProviderFactory.get_provider(
                product.tenant,
                model_name='gpt-4o-mini'  # Use cheaper model for analysis
            )
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a product analyst. Analyze products and extract structured information.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse response
            analysis_data = cls._parse_analysis_response(response['content'])
            
            # Generate embedding
            embedding_text = f"{product.name} {product.description} {' '.join(analysis_data['key_features'])}"
            embedding = EmbeddingService.generate_embedding(embedding_text)
            
            # Save or update analysis
            analysis, created = ProductAnalysis.objects.update_or_create(
                product=product,
                defaults={
                    'key_features': analysis_data['key_features'],
                    'use_cases': analysis_data['use_cases'],
                    'target_audience': analysis_data['target_audience'],
                    'summary': analysis_data['summary'],
                    'ai_categories': analysis_data['ai_categories'],
                    'ai_tags': analysis_data['ai_tags'],
                    'embedding': embedding,
                }
            )
            
            logger.info(f"Product analysis {'created' if created else 'updated'}: {product.name}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing product {product.id}: {e}")
            raise
    
    @classmethod
    def match_need_to_products(cls, tenant, need_description, limit=5):
        """
        Match customer need to products using semantic search.
        
        Args:
            tenant: Tenant instance
            need_description: Customer's description of what they need
            limit: Maximum number of products to return
        
        Returns:
            List of dicts with product and match score
        """
        # Generate embedding for need
        need_embedding = EmbeddingService.generate_embedding(need_description)
        
        # Get all analyzed products for tenant
        analyses = ProductAnalysis.objects.filter(
            product__tenant=tenant,
            product__is_active=True,
            embedding__isnull=False
        ).select_related('product')
        
        # Calculate similarity scores
        matches = []
        for analysis in analyses:
            if analysis.embedding:
                similarity = EmbeddingService.cosine_similarity(
                    need_embedding,
                    analysis.embedding
                )
                matches.append({
                    'product': analysis.product,
                    'analysis': analysis,
                    'score': similarity,
                })
        
        # Sort by score and return top matches
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:limit]
    
    @classmethod
    def generate_recommendation_explanation(cls, product, analysis, customer_need):
        """
        Generate explanation for why product is recommended.
        
        Args:
            product: Product instance
            analysis: ProductAnalysis instance
            customer_need: Customer's stated need
        
        Returns:
            str explanation
        """
        prompt = f"""
        Explain why this product matches the customer's need.
        
        Customer Need: {customer_need}
        
        Product: {product.name}
        Description: {product.description}
        Key Features: {', '.join(analysis.key_features)}
        Use Cases: {', '.join(analysis.use_cases)}
        
        Generate a brief, friendly explanation (2-3 sentences) of why this product is a good match.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(
                product.tenant,
                model_name='gpt-4o-mini'
            )
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a helpful product advisor.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            return response['content'].strip()
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback to simple explanation
            return f"This product matches your need because it {analysis.use_cases[0] if analysis.use_cases else 'is suitable for your requirements'}."
    
    @classmethod
    def extract_distinguishing_features(cls, products):
        """
        Extract features that distinguish products from each other.
        
        Args:
            products: List of Product instances
        
        Returns:
            dict mapping product_id to list of distinguishing features
        """
        if len(products) < 2:
            return {}
        
        # Get analyses
        analyses = {
            p.id: ProductAnalysis.objects.filter(product=p).first()
            for p in products
        }
        
        # Find unique features for each product
        distinguishing = {}
        for product in products:
            analysis = analyses.get(product.id)
            if not analysis:
                continue
            
            unique_features = []
            for feature in analysis.key_features:
                # Check if feature is unique to this product
                is_unique = True
                for other_product in products:
                    if other_product.id == product.id:
                        continue
                    other_analysis = analyses.get(other_product.id)
                    if other_analysis and feature in other_analysis.key_features:
                        is_unique = False
                        break
                
                if is_unique:
                    unique_features.append(feature)
            
            distinguishing[product.id] = unique_features
        
        return distinguishing
    
    @classmethod
    def _build_analysis_prompt(cls, product):
        """Build prompt for product analysis."""
        return f"""
        Analyze this product and extract structured information.
        
        Product Name: {product.name}
        Description: {product.description}
        Price: {product.price} {product.tenant.currency}
        Category: {product.category.name if product.category else 'N/A'}
        
        Provide your analysis in JSON format with these fields:
        - key_features: List of 3-5 key product features
        - use_cases: List of 2-3 common use cases
        - target_audience: List of 1-2 target customer segments
        - summary: Brief 1-sentence product summary
        - ai_categories: List of 2-3 informal categories (e.g., "gift items", "daily essentials")
        - ai_tags: List of 3-5 searchable tags
        
        Return ONLY valid JSON, no other text.
        """
    
    @classmethod
    def _parse_analysis_response(cls, response_text):
        """Parse LLM response into structured data."""
        try:
            # Try to parse as JSON
            data = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['key_features', 'use_cases', 'target_audience', 'summary', 'ai_categories', 'ai_tags']
            for field in required_fields:
                if field not in data:
                    data[field] = [] if field != 'summary' else ''
            
            return data
            
        except json.JSONDecodeError:
            # Fallback: extract what we can
            logger.warning("Failed to parse analysis as JSON, using fallback")
            return {
                'key_features': [],
                'use_cases': [],
                'target_audience': [],
                'summary': response_text[:200],
                'ai_categories': [],
                'ai_tags': [],
            }
