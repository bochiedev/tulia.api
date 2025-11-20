"""
Grounded Response Validator Service.

Ensures AI agent responses only contain factual information that can be
verified against the actual data in the knowledge base and catalog.

This service prevents hallucinations by:
1. Extracting factual claims from responses
2. Verifying each claim against context data
3. Flagging or removing unverifiable claims
4. Logging validation failures for monitoring
"""
import logging
import re
from typing import List, Tuple, Dict, Any, Optional
from decimal import Decimal

from apps.bot.services.context_builder_service import AgentContext

logger = logging.getLogger(__name__)


class GroundedResponseValidator:
    """
    Service for validating AI responses are grounded in actual data.
    
    Prevents hallucinations by ensuring all factual claims in responses
    can be verified against the provided context (products, services,
    knowledge base, etc.).
    """
    
    # Patterns for extracting factual claims
    PRICE_PATTERN = re.compile(r'(?:costs?|priced? at|is|are)\s+(?:about\s+)?(?:KES|USD|EUR|GBP|\$|€|£)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE)
    STOCK_PATTERN = re.compile(r'(?:in stock|available|have|has)\s+(\d+)', re.IGNORECASE)
    AVAILABILITY_PATTERN = re.compile(r'(?:is|are)\s+(?:currently\s+)?(?:available|in stock|out of stock|unavailable)', re.IGNORECASE)
    FEATURE_PATTERN = re.compile(r'(?:has|have|includes?|comes? with|features?)\s+([^.!?]+)', re.IGNORECASE)
    
    def __init__(self):
        """Initialize the validator."""
        self.validation_stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'claims_extracted': 0,
            'claims_verified': 0,
            'claims_failed': 0
        }
    
    def validate_response(
        self,
        response: str,
        context: AgentContext
    ) -> Tuple[bool, List[str]]:
        """
        Validate that response is grounded in context data.
        
        Extracts factual claims from the response and verifies each
        against the provided context. Returns validation result and
        list of issues found.
        
        Args:
            response: AI-generated response text
            context: AgentContext with all available data
            
        Returns:
            Tuple of (is_valid: bool, issues: List[str])
            where is_valid is True if all claims verified,
            and issues contains descriptions of any problems found
        """
        self.validation_stats['total_validations'] += 1
        
        logger.debug(f"Validating response: '{response[:100]}...'")
        
        # Extract claims from response
        claims = self.extract_claims(response)
        self.validation_stats['claims_extracted'] += len(claims)
        
        if not claims:
            # No factual claims to verify
            logger.debug("No factual claims found in response")
            self.validation_stats['passed_validations'] += 1
            return True, []
        
        logger.debug(f"Extracted {len(claims)} claims to verify")
        
        # Verify each claim
        issues = []
        for claim in claims:
            is_verified = self.verify_claim(claim, context)
            
            if is_verified:
                self.validation_stats['claims_verified'] += 1
            else:
                self.validation_stats['claims_failed'] += 1
                issues.append(f"Unverifiable claim: {claim}")
                logger.warning(f"Failed to verify claim: {claim}")
        
        # Overall validation result
        is_valid = len(issues) == 0
        
        if is_valid:
            self.validation_stats['passed_validations'] += 1
            logger.info("Response validation passed")
        else:
            self.validation_stats['failed_validations'] += 1
            logger.warning(f"Response validation failed with {len(issues)} issues")
        
        return is_valid, issues
    
    def extract_claims(self, response: str) -> List[str]:
        """
        Extract factual claims from response text.
        
        Identifies statements that make specific factual assertions
        about products, services, prices, availability, features, etc.
        
        Args:
            response: Response text to analyze
            
        Returns:
            List of extracted claim strings
        """
        claims = []
        
        # Split response into sentences
        sentences = re.split(r'[.!?]+', response)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check for price claims
            if self.PRICE_PATTERN.search(sentence):
                claims.append(sentence)
                continue
            
            # Check for stock/quantity claims
            if self.STOCK_PATTERN.search(sentence):
                claims.append(sentence)
                continue
            
            # Check for availability claims
            if self.AVAILABILITY_PATTERN.search(sentence):
                claims.append(sentence)
                continue
            
            # Check for product/service existence claims BEFORE feature claims
            # (to avoid misclassifying "we have products" as a feature claim)
            if any(word in sentence.lower() for word in ['we have', 'we offer', 'we sell']):
                claims.append(sentence)
                continue
            
            # Check for feature claims
            if self.FEATURE_PATTERN.search(sentence):
                claims.append(sentence)
                continue
        
        logger.debug(f"Extracted {len(claims)} claims from response")
        return claims
    
    def verify_claim(self, claim: str, context: AgentContext) -> bool:
        """
        Verify a single claim against context data.
        
        Checks if the claim can be substantiated by data in the context
        (products, services, knowledge base, etc.).
        
        Args:
            claim: Claim text to verify
            context: AgentContext with available data
            
        Returns:
            True if claim is verified, False otherwise
        """
        claim_lower = claim.lower()
        
        # Verify price claims
        if self._is_price_claim(claim):
            return self._verify_price_claim(claim, context)
        
        # Verify stock/availability claims
        if self._is_availability_claim(claim):
            return self._verify_availability_claim(claim, context)
        
        # Verify product/service existence claims BEFORE feature claims
        # (to avoid misclassifying "we have products" as a feature claim)
        if self._is_existence_claim(claim):
            return self._verify_existence_claim(claim, context)
        
        # Verify feature claims
        if self._is_feature_claim(claim):
            return self._verify_feature_claim(claim, context)
        
        # If we can't categorize the claim, be conservative and mark as unverified
        logger.debug(f"Could not categorize claim for verification: {claim}")
        return False
    
    def _is_price_claim(self, claim: str) -> bool:
        """Check if claim is about pricing."""
        return bool(self.PRICE_PATTERN.search(claim))
    
    def _is_availability_claim(self, claim: str) -> bool:
        """Check if claim is about availability/stock."""
        return bool(self.AVAILABILITY_PATTERN.search(claim) or self.STOCK_PATTERN.search(claim))
    
    def _is_feature_claim(self, claim: str) -> bool:
        """Check if claim is about product/service features."""
        return bool(self.FEATURE_PATTERN.search(claim))
    
    def _is_existence_claim(self, claim: str) -> bool:
        """Check if claim asserts existence of product/service."""
        existence_keywords = ['we have', 'we offer', 'we sell', 'available', 'in stock']
        return any(keyword in claim.lower() for keyword in existence_keywords)
    
    def _verify_price_claim(self, claim: str, context: AgentContext) -> bool:
        """
        Verify a price claim against catalog data.
        
        Args:
            claim: Price claim to verify
            context: AgentContext with catalog data
            
        Returns:
            True if price matches a product/service in catalog
        """
        # Extract price from claim
        match = self.PRICE_PATTERN.search(claim)
        if not match:
            return False
        
        claimed_price_str = match.group(1).replace(',', '')
        try:
            claimed_price = Decimal(claimed_price_str)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse price from claim: {claimed_price_str}")
            return False
        
        claim_lower = claim.lower()
        
        # Check against products
        for product in context.catalog_context.products:
            # First check if the price matches (allow up to 1 cent difference for rounding)
            if abs(product.price - claimed_price) <= Decimal('0.01'):
                product_title_lower = product.title.lower()
                
                # Then check if the product is mentioned in the claim
                # Try full title match first (most reliable)
                if product_title_lower in claim_lower:
                    logger.debug(f"Price claim verified against product (full title match): {product.title}")
                    return True
                
                # Try matching individual words (for partial mentions)
                product_words = [w for w in product_title_lower.split() if len(w) > 1]
                if not product_words:
                    # If all words are 1-2 chars, the full title match above should have caught it
                    # If we're here, it means the title wasn't found, so this is a mismatch
                    logger.debug(f"Short product title '{product.title}' not found in claim")
                    continue
                
                # Count how many product words appear in claim
                matching_words = sum(1 for word in product_words if word in claim_lower)
                # If more than half the words match, consider it a match
                if matching_words > 0 and matching_words >= len(product_words) / 2:
                    logger.debug(f"Price claim verified against product (partial match): {product.title}")
                    return True
        
        # Check against services
        for service in context.catalog_context.services:
            if abs(service.price - claimed_price) <= Decimal('0.01'):
                # Check if service is mentioned
                if service.title.lower() in claim_lower:
                    logger.debug(f"Price claim verified against service: {service.title}")
                    return True
                # Try partial match for services too
                service_words = service.title.lower().split()
                matching_words = sum(1 for word in service_words if word in claim_lower and len(word) > 1)
                if matching_words > 0 and matching_words >= len(service_words) / 2:
                    logger.debug(f"Price claim verified against service (partial match): {service.title}")
                    return True
        
        # Check if last viewed item matches
        if context.last_product_viewed:
            if abs(context.last_product_viewed.price - claimed_price) <= Decimal('0.01'):
                logger.debug(f"Price claim verified against last viewed product")
                return True
        
        if context.last_service_viewed:
            if abs(context.last_service_viewed.price - claimed_price) <= Decimal('0.01'):
                logger.debug(f"Price claim verified against last viewed service")
                return True
        
        logger.warning(f"Could not verify price claim: {claimed_price}")
        return False
    
    def _verify_availability_claim(self, claim: str, context: AgentContext) -> bool:
        """
        Verify an availability claim against catalog data.
        
        Args:
            claim: Availability claim to verify
            context: AgentContext with catalog data
            
        Returns:
            True if availability status matches catalog
        """
        claim_lower = claim.lower()
        
        # Determine claimed availability status
        is_claiming_available = any(word in claim_lower for word in ['available', 'in stock', 'have'])
        is_claiming_unavailable = any(word in claim_lower for word in ['out of stock', 'unavailable', 'not available'])
        
        if not (is_claiming_available or is_claiming_unavailable):
            return False
        
        # Extract product/service name from claim
        # This is a simplified approach - in production, you'd want more sophisticated NER
        words = claim.split()
        
        # Check products
        for product in context.catalog_context.products:
            # Check if product name appears in claim
            product_words = product.title.lower().split()
            # Check if any significant word from product name appears in claim
            # Use length > 2 instead of > 3 to catch short product names
            if any(word in claim_lower for word in product_words if len(word) > 2):
                # Verify availability status matches
                product_available = product.stock > 0
                
                if is_claiming_available and product_available:
                    logger.debug(f"Availability claim verified for product: {product.title}")
                    return True
                elif is_claiming_unavailable and not product_available:
                    logger.debug(f"Unavailability claim verified for product: {product.title}")
                    return True
            # Also check if the full product title appears in the claim
            elif product.title.lower() in claim_lower:
                product_available = product.stock > 0
                if (is_claiming_available and product_available) or (is_claiming_unavailable and not product_available):
                    logger.debug(f"Availability claim verified for product (full title match): {product.title}")
                    return True
        
        # Check services (services are typically always available unless explicitly marked)
        for service in context.catalog_context.services:
            service_words = service.title.lower().split()
            if any(word in claim_lower for word in service_words):
                # Services are generally available if active
                if is_claiming_available and service.is_active:
                    logger.debug(f"Availability claim verified for service: {service.title}")
                    return True
        
        # Check last viewed items
        if context.last_product_viewed:
            product_words = context.last_product_viewed.title.lower().split()
            if any(word in claim_lower for word in product_words):
                product_available = context.last_product_viewed.stock > 0
                if (is_claiming_available and product_available) or (is_claiming_unavailable and not product_available):
                    logger.debug(f"Availability claim verified for last viewed product")
                    return True
        
        # If claim is generic (not about specific item), check if ANY items match the claim
        if not any(word in claim_lower for word in ['the', 'this', 'that']):
            # Generic claim like "we have products available"
            if is_claiming_available and len(context.catalog_context.products) > 0:
                logger.debug("Generic availability claim verified")
                return True
        
        logger.warning(f"Could not verify availability claim: {claim}")
        return False
    
    def _verify_feature_claim(self, claim: str, context: AgentContext) -> bool:
        """
        Verify a feature claim against product/service data.
        
        Args:
            claim: Feature claim to verify
            context: AgentContext with catalog data
            
        Returns:
            True if feature is present in product/service data
        """
        claim_lower = claim.lower()
        
        # Extract feature description
        match = self.FEATURE_PATTERN.search(claim)
        if not match:
            return False
        
        feature_text = match.group(1).strip().lower()
        
        # Check products
        for product in context.catalog_context.products:
            # Check description - use substring matching
            if product.description:
                desc_lower = product.description.lower()
                # Check if feature text is a substring of description
                if feature_text in desc_lower:
                    logger.debug(f"Feature claim verified in product description: {product.title}")
                    return True
                # Also check if description words appear in feature text (for short descriptions)
                desc_words = [w for w in desc_lower.split() if len(w) > 1]
                if desc_words:
                    matching_words = sum(1 for word in desc_words if word in feature_text)
                    if matching_words > 0 and matching_words >= len(desc_words) / 2:
                        logger.debug(f"Feature claim verified in product description (partial): {product.title}")
                        return True
            
            # Check metadata
            if product.metadata:
                metadata_str = str(product.metadata).lower()
                if feature_text in metadata_str:
                    logger.debug(f"Feature claim verified in product metadata: {product.title}")
                    return True
        
        # Check services
        for service in context.catalog_context.services:
            # Check description
            if service.description:
                desc_lower = service.description.lower()
                if feature_text in desc_lower:
                    logger.debug(f"Feature claim verified in service description: {service.title}")
                    return True
                # Also check partial match
                desc_words = [w for w in desc_lower.split() if len(w) > 1]
                if desc_words:
                    matching_words = sum(1 for word in desc_words if word in feature_text)
                    if matching_words > 0 and matching_words >= len(desc_words) / 2:
                        logger.debug(f"Feature claim verified in service description (partial): {service.title}")
                        return True
            
            # Check metadata
            if service.metadata:
                metadata_str = str(service.metadata).lower()
                if feature_text in metadata_str:
                    logger.debug(f"Feature claim verified in service metadata: {service.title}")
                    return True
        
        # Check last viewed items
        if context.last_product_viewed:
            if context.last_product_viewed.description:
                desc_lower = context.last_product_viewed.description.lower()
                if feature_text in desc_lower:
                    logger.debug(f"Feature claim verified in last viewed product")
                    return True
        
        if context.last_service_viewed:
            if context.last_service_viewed.description:
                desc_lower = context.last_service_viewed.description.lower()
                if feature_text in desc_lower:
                    logger.debug(f"Feature claim verified in last viewed service")
                    return True
        
        logger.warning(f"Could not verify feature claim: {feature_text}")
        return False
    
    def _verify_existence_claim(self, claim: str, context: AgentContext) -> bool:
        """
        Verify a claim about product/service existence.
        
        Args:
            claim: Existence claim to verify
            context: AgentContext with catalog data
            
        Returns:
            True if claimed items exist in catalog
        """
        claim_lower = claim.lower()
        
        # Extract potential product/service names
        # This is simplified - in production, use NER
        words = claim_lower.split()
        
        # Check if any products match
        for product in context.catalog_context.products:
            product_words = product.title.lower().split()
            # Check if significant words from product name appear in claim
            # Use length > 2 instead of > 3 to catch short product names
            if any(word in claim_lower for word in product_words if len(word) > 2):
                logger.debug(f"Existence claim verified for product: {product.title}")
                return True
            # Also check if the full product title appears in the claim
            elif product.title.lower() in claim_lower:
                logger.debug(f"Existence claim verified for product (full title match): {product.title}")
                return True
        
        # Check if any services match
        for service in context.catalog_context.services:
            service_words = service.title.lower().split()
            if any(word in claim_lower for word in service_words if len(word) > 3):
                logger.debug(f"Existence claim verified for service: {service.title}")
                return True
        
        # If claim is very generic ("we have products"), verify we have items
        generic_claims = ['products', 'services', 'items', 'offerings']
        if any(generic in claim_lower for generic in generic_claims):
            if len(context.catalog_context.products) > 0 or len(context.catalog_context.services) > 0:
                logger.debug("Generic existence claim verified")
                return True
        
        logger.warning(f"Could not verify existence claim: {claim}")
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return self.validation_stats.copy()
    
    def reset_stats(self):
        """Reset validation statistics."""
        self.validation_stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'claims_extracted': 0,
            'claims_verified': 0,
            'claims_failed': 0
        }


def create_grounded_response_validator() -> GroundedResponseValidator:
    """Factory function to create GroundedResponseValidator instance."""
    return GroundedResponseValidator()
