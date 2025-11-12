"""
Campaign service for creating and executing message campaigns.

Handles campaign creation, targeting, execution, and A/B testing.
"""
import logging
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from apps.messaging.models import MessageCampaign, Message, Conversation
from apps.messaging.services.messaging_service import MessagingService
from apps.messaging.services.consent_service import ConsentService
from apps.tenants.models import Customer

logger = logging.getLogger(__name__)


class CampaignService:
    """
    Service for managing message campaigns.
    
    Provides methods for:
    - Creating campaigns with validation
    - Calculating reach based on target criteria
    - Executing campaigns with consent filtering
    - A/B test variant assignment
    - Tracking delivery and engagement metrics
    """
    
    def __init__(self):
        self.messaging_service = MessagingService()
        self.consent_service = ConsentService()
    
    def create_campaign(
        self,
        tenant,
        name: str,
        message_content: str,
        target_criteria: Dict,
        created_by=None,
        template=None,
        scheduled_at=None,
        is_ab_test: bool = False,
        variants: List[Dict] = None,
        description: str = ""
    ) -> MessageCampaign:
        """
        Create a new message campaign with validation.
        
        Args:
            tenant: Tenant creating the campaign
            name: Campaign name
            message_content: Default message content
            target_criteria: Dict with targeting rules (tags, purchase_history, activity)
            created_by: User creating the campaign
            template: Optional MessageTemplate to use
            scheduled_at: Optional datetime to schedule execution
            is_ab_test: Whether this is an A/B test
            variants: List of variant dicts for A/B testing
            description: Campaign description
            
        Returns:
            MessageCampaign: Created campaign instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate scheduled_at is in future if provided
        if scheduled_at and scheduled_at <= timezone.now():
            raise ValueError("scheduled_at must be in the future")
        
        # Validate A/B test configuration
        if is_ab_test:
            if not variants or len(variants) < 2:
                raise ValueError("A/B test requires at least 2 variants")
            
            # Check tier limits for variant count
            try:
                subscription = tenant.subscription
                if subscription:
                    tier = subscription.tier
                    max_variants = tier.ab_test_variants if hasattr(tier, 'ab_test_variants') else 2
                    if len(variants) > max_variants:
                        raise ValueError(
                            f"Your subscription tier allows maximum {max_variants} variants. "
                            f"Upgrade to test more variants."
                        )
            except Exception:
                # No subscription found, use default limit
                max_variants = 2
                if len(variants) > max_variants:
                    raise ValueError(
                        f"Maximum {max_variants} variants allowed. "
                        f"Upgrade to test more variants."
                    )
        
        # Validate target criteria
        if not target_criteria:
            target_criteria = {}  # Empty criteria = all customers
        
        # Create campaign
        campaign = MessageCampaign.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            message_content=message_content,
            template=template,
            target_criteria=target_criteria,
            is_ab_test=is_ab_test,
            variants=variants or [],
            scheduled_at=scheduled_at,
            status='scheduled' if scheduled_at else 'draft',
            created_by=created_by
        )
        
        logger.info(
            f"Created campaign {campaign.id} for tenant {tenant.slug}: {name}",
            extra={'tenant_id': str(tenant.id), 'campaign_id': str(campaign.id)}
        )
        
        return campaign
    
    def calculate_reach(self, tenant, target_criteria: Dict) -> Tuple[int, int]:
        """
        Calculate how many customers match the targeting criteria.
        
        Args:
            tenant: Tenant to calculate reach for
            target_criteria: Dict with targeting rules
            
        Returns:
            Tuple[int, int]: (total_matching, with_consent)
            
        Target criteria format:
        {
            "tags": ["vip", "new_customer"],  # Customers with any of these tags
            "purchase_history": {
                "ordered_in_last_days": 30,  # Customers who ordered recently
                "min_order_count": 1
            },
            "conversation_activity": {
                "active_in_last_days": 7,  # Customers with recent activity
                "status": ["open", "bot"]
            }
        }
        """
        # Start with all customers for this tenant
        queryset = Customer.objects.filter(tenant=tenant, is_active=True)
        
        # Apply tag filtering
        if 'tags' in target_criteria and target_criteria['tags']:
            tags = target_criteria['tags']
            # Filter customers who have any of the specified tags
            tag_queries = [Q(tags__contains=tag) for tag in tags]
            tag_filter = tag_queries[0]
            for q in tag_queries[1:]:
                tag_filter |= q
            queryset = queryset.filter(tag_filter)
        
        # Apply purchase history filtering
        if 'purchase_history' in target_criteria:
            purchase_config = target_criteria['purchase_history']
            
            if 'ordered_in_last_days' in purchase_config:
                days = purchase_config['ordered_in_last_days']
                cutoff = timezone.now() - timezone.timedelta(days=days)
                queryset = queryset.filter(
                    orders__created_at__gte=cutoff
                ).distinct()
            
            if 'min_order_count' in purchase_config:
                min_count = purchase_config['min_order_count']
                queryset = queryset.annotate(
                    order_count=Count('orders')
                ).filter(order_count__gte=min_count)
        
        # Apply conversation activity filtering
        if 'conversation_activity' in target_criteria:
            activity_config = target_criteria['conversation_activity']
            
            if 'active_in_last_days' in activity_config:
                days = activity_config['active_in_last_days']
                cutoff = timezone.now() - timezone.timedelta(days=days)
                queryset = queryset.filter(
                    conversations__updated_at__gte=cutoff
                ).distinct()
            
            if 'status' in activity_config:
                statuses = activity_config['status']
                queryset = queryset.filter(
                    conversations__status__in=statuses
                ).distinct()
        
        # Count total matching customers
        total_matching = queryset.count()
        
        # Count customers with promotional consent
        with_consent = 0
        for customer in queryset:
            prefs = self.consent_service.get_preferences(tenant, customer)
            if prefs and prefs.promotional_messages:
                with_consent += 1
        
        logger.info(
            f"Campaign reach for tenant {tenant.slug}: {total_matching} total, {with_consent} with consent",
            extra={
                'tenant_id': str(tenant.id),
                'total_matching': total_matching,
                'with_consent': with_consent
            }
        )
        
        return total_matching, with_consent
    
    def execute_campaign(self, campaign: MessageCampaign) -> Dict:
        """
        Execute a campaign by sending messages to all matching customers with consent.
        
        Args:
            campaign: MessageCampaign to execute
            
        Returns:
            Dict with execution results:
            {
                'targeted': int,
                'sent': int,
                'failed': int,
                'skipped_no_consent': int,
                'errors': List[str]
            }
            
        Raises:
            ValueError: If campaign is not in valid state for execution
        """
        # Validate campaign state
        if campaign.status not in ['draft', 'scheduled']:
            raise ValueError(f"Cannot execute campaign in status: {campaign.status}")
        
        # Check subscription tier limits
        try:
            subscription = campaign.tenant.subscription
            if subscription:
                tier = subscription.tier
                if hasattr(tier, 'max_campaign_sends') and tier.max_campaign_sends:
                    # Check if tenant has exceeded monthly campaign limit
                    # This would require tracking monthly sends - simplified for now
                    pass
        except Exception:
            # No subscription found, continue
            pass
        
        # Mark campaign as sending
        campaign.mark_sending()
        
        # Get matching customers
        queryset = Customer.objects.filter(
            tenant=campaign.tenant
        )
        
        # Apply target criteria filtering
        queryset = self._apply_target_criteria(queryset, campaign.target_criteria)
        
        # Prepare A/B test variants if applicable
        if campaign.is_ab_test and campaign.variants:
            customer_assignments = self._assign_ab_variants(
                list(queryset),
                campaign.variants
            )
        else:
            customer_assignments = {customer.id: None for customer in queryset}
        
        # Execute campaign
        results = {
            'targeted': 0,
            'sent': 0,
            'failed': 0,
            'skipped_no_consent': 0,
            'errors': []
        }
        
        for customer in queryset:
            results['targeted'] += 1
            campaign.increment_delivery()
            
            # Check consent
            prefs = self.consent_service.get_preferences(campaign.tenant, customer)
            if not prefs or not prefs.promotional_messages:
                results['skipped_no_consent'] += 1
                continue
            
            # Get message content (variant or default)
            variant_index = customer_assignments.get(customer.id)
            if variant_index is not None and campaign.variants:
                message_content = campaign.variants[variant_index].get(
                    'content',
                    campaign.message_content
                )
            else:
                message_content = campaign.message_content
            
            # Send message
            try:
                # Get or create conversation
                conversation, _ = Conversation.objects.get_or_create(
                    tenant=campaign.tenant,
                    customer=customer,
                    defaults={'status': 'open', 'channel': 'whatsapp'}
                )
                
                # Send via messaging service
                message = self.messaging_service.send_message(
                    tenant=campaign.tenant,
                    customer=customer,
                    content=message_content,
                    message_type='scheduled_promotional',
                    template_id=campaign.template.id if campaign.template else None,
                    conversation=conversation
                )
                
                if message:
                    results['sent'] += 1
                    campaign.increment_delivered()
                    
                    # Track variant assignment in campaign metadata
                    if variant_index is not None:
                        if 'variant_customers' not in campaign.metadata:
                            campaign.metadata['variant_customers'] = {}
                        variant_key = f"variant_{variant_index}"
                        if variant_key not in campaign.metadata['variant_customers']:
                            campaign.metadata['variant_customers'][variant_key] = []
                        campaign.metadata['variant_customers'][variant_key].append(str(customer.id))
                        campaign.save(update_fields=['metadata'])
                else:
                    results['failed'] += 1
                    campaign.increment_failed()
                    
            except Exception as e:
                results['failed'] += 1
                campaign.increment_failed()
                error_msg = f"Failed to send to customer {customer.id}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(
                    error_msg,
                    extra={
                        'tenant_id': str(campaign.tenant.id),
                        'campaign_id': str(campaign.id),
                        'customer_id': str(customer.id)
                    },
                    exc_info=True
                )
        
        # Mark campaign as completed
        campaign.mark_completed()
        
        logger.info(
            f"Campaign {campaign.id} execution completed: {results['sent']} sent, "
            f"{results['failed']} failed, {results['skipped_no_consent']} skipped",
            extra={
                'tenant_id': str(campaign.tenant.id),
                'campaign_id': str(campaign.id),
                'results': results
            }
        )
        
        return results
    
    def _apply_target_criteria(self, queryset, target_criteria: Dict):
        """Apply target criteria filters to customer queryset."""
        if not target_criteria:
            return queryset
        
        # Apply tag filtering
        if 'tags' in target_criteria and target_criteria['tags']:
            tags = target_criteria['tags']
            tag_queries = [Q(tags__contains=tag) for tag in tags]
            tag_filter = tag_queries[0]
            for q in tag_queries[1:]:
                tag_filter |= q
            queryset = queryset.filter(tag_filter)
        
        # Apply purchase history filtering
        if 'purchase_history' in target_criteria:
            purchase_config = target_criteria['purchase_history']
            
            if 'ordered_in_last_days' in purchase_config:
                days = purchase_config['ordered_in_last_days']
                cutoff = timezone.now() - timezone.timedelta(days=days)
                queryset = queryset.filter(
                    orders__created_at__gte=cutoff
                ).distinct()
            
            if 'min_order_count' in purchase_config:
                min_count = purchase_config['min_order_count']
                queryset = queryset.annotate(
                    order_count=Count('orders')
                ).filter(order_count__gte=min_count)
        
        # Apply conversation activity filtering
        if 'conversation_activity' in target_criteria:
            activity_config = target_criteria['conversation_activity']
            
            if 'active_in_last_days' in activity_config:
                days = activity_config['active_in_last_days']
                cutoff = timezone.now() - timezone.timedelta(days=days)
                queryset = queryset.filter(
                    conversations__updated_at__gte=cutoff
                ).distinct()
            
            if 'status' in activity_config:
                statuses = activity_config['status']
                queryset = queryset.filter(
                    conversations__status__in=statuses
                ).distinct()
        
        return queryset
    
    def _assign_ab_variants(
        self,
        customers: List[Customer],
        variants: List[Dict]
    ) -> Dict[str, int]:
        """
        Assign customers to A/B test variants with equal distribution.
        
        Args:
            customers: List of Customer objects
            variants: List of variant configurations
            
        Returns:
            Dict mapping customer_id to variant_index
        """
        import random
        
        assignments = {}
        variant_count = len(variants)
        
        # Shuffle customers for random assignment
        shuffled = customers.copy()
        random.shuffle(shuffled)
        
        # Assign customers to variants in round-robin fashion
        for idx, customer in enumerate(shuffled):
            variant_index = idx % variant_count
            assignments[customer.id] = variant_index
        
        return assignments
    
    def track_message_read(self, campaign: MessageCampaign, message: Message):
        """
        Track when a campaign message is read.
        
        Args:
            campaign: MessageCampaign instance
            message: Message that was read
        """
        campaign.increment_read()
        logger.debug(
            f"Campaign {campaign.id} message read",
            extra={
                'campaign_id': str(campaign.id),
                'message_id': str(message.id)
            }
        )
    
    def track_message_response(self, campaign: MessageCampaign, message: Message):
        """
        Track when a customer responds to a campaign message.
        
        Args:
            campaign: MessageCampaign instance
            message: Response message from customer
        """
        campaign.increment_response()
        logger.debug(
            f"Campaign {campaign.id} received response",
            extra={
                'campaign_id': str(campaign.id),
                'message_id': str(message.id)
            }
        )
    
    def track_conversion(self, campaign: MessageCampaign, reference_type: str, reference_id: str):
        """
        Track a conversion (order or booking) from a campaign.
        
        Args:
            campaign: MessageCampaign instance
            reference_type: Type of conversion ('order' or 'appointment')
            reference_id: ID of the order or appointment
        """
        campaign.increment_conversion()
        logger.info(
            f"Campaign {campaign.id} conversion tracked: {reference_type} {reference_id}",
            extra={
                'campaign_id': str(campaign.id),
                'reference_type': reference_type,
                'reference_id': reference_id
            }
        )
    
    def generate_report(self, campaign: MessageCampaign) -> Dict:
        """
        Generate comprehensive analytics report for a campaign.
        
        Args:
            campaign: MessageCampaign to generate report for
            
        Returns:
            Dict with campaign metrics and analytics:
            {
                'campaign_id': str,
                'name': str,
                'status': str,
                'created_at': datetime,
                'started_at': datetime,
                'completed_at': datetime,
                'duration_seconds': int,
                'targeting': {
                    'criteria': dict,
                    'total_targeted': int
                },
                'delivery': {
                    'delivery_count': int,
                    'delivered_count': int,
                    'failed_count': int,
                    'delivery_rate': float
                },
                'engagement': {
                    'read_count': int,
                    'read_rate': float,
                    'response_count': int,
                    'engagement_rate': float,
                    'conversion_count': int,
                    'conversion_rate': float
                },
                'ab_test': {
                    'is_ab_test': bool,
                    'variants': List[Dict]  # If A/B test
                }
            }
        """
        # Calculate duration
        duration_seconds = None
        if campaign.started_at and campaign.completed_at:
            duration = campaign.completed_at - campaign.started_at
            duration_seconds = int(duration.total_seconds())
        
        # Base report
        report = {
            'campaign_id': str(campaign.id),
            'name': campaign.name,
            'description': campaign.description,
            'status': campaign.status,
            'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
            'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
            'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None,
            'duration_seconds': duration_seconds,
            'targeting': {
                'criteria': campaign.target_criteria,
                'total_targeted': campaign.delivery_count
            },
            'delivery': {
                'delivery_count': campaign.delivery_count,
                'delivered_count': campaign.delivered_count,
                'failed_count': campaign.failed_count,
                'delivery_rate': campaign.calculate_delivery_rate()
            },
            'engagement': {
                'read_count': campaign.read_count,
                'read_rate': campaign.calculate_read_rate(),
                'response_count': campaign.response_count,
                'engagement_rate': campaign.calculate_engagement_rate(),
                'conversion_count': campaign.conversion_count,
                'conversion_rate': campaign.calculate_conversion_rate()
            }
        }
        
        # Add A/B test analytics if applicable
        if campaign.is_ab_test and campaign.variants:
            report['ab_test'] = {
                'is_ab_test': True,
                'variants': self._generate_variant_analytics(campaign)
            }
        else:
            report['ab_test'] = {
                'is_ab_test': False,
                'variants': []
            }
        
        return report
    
    def _generate_variant_analytics(self, campaign: MessageCampaign) -> List[Dict]:
        """
        Generate analytics for each A/B test variant.
        
        Args:
            campaign: MessageCampaign with A/B test
            
        Returns:
            List of variant analytics dicts
        """
        variant_analytics = []
        
        # Get variant customer assignments from metadata
        variant_customers = campaign.metadata.get('variant_customers', {})
        
        for idx, variant in enumerate(campaign.variants):
            variant_key = f"variant_{idx}"
            customer_ids = variant_customers.get(variant_key, [])
            
            # Count messages for this variant
            variant_messages = Message.objects.filter(
                conversation__tenant=campaign.tenant,
                conversation__customer_id__in=customer_ids,
                message_type='scheduled_promotional',
                created_at__gte=campaign.started_at if campaign.started_at else campaign.created_at,
                created_at__lte=campaign.completed_at if campaign.completed_at else timezone.now()
            )
            
            # Calculate variant metrics
            delivered = variant_messages.filter(delivered_at__isnull=False).count()
            read = variant_messages.filter(read_at__isnull=False).count()
            
            # Count responses (inbound messages after campaign message)
            response_count = 0
            for msg in variant_messages:
                responses = Message.objects.filter(
                    conversation=msg.conversation,
                    direction='in',
                    created_at__gt=msg.created_at,
                    created_at__lte=msg.created_at + timezone.timedelta(hours=24)
                ).count()
                response_count += min(responses, 1)  # Count max 1 response per message
            
            # Calculate rates
            delivery_rate = (delivered / len(customer_ids) * 100) if customer_ids else 0
            read_rate = (read / delivered * 100) if delivered > 0 else 0
            engagement_rate = (response_count / delivered * 100) if delivered > 0 else 0
            
            # Calculate average response time
            avg_response_time = None
            response_times = []
            for msg in variant_messages:
                first_response = Message.objects.filter(
                    conversation=msg.conversation,
                    direction='in',
                    created_at__gt=msg.created_at,
                    created_at__lte=msg.created_at + timezone.timedelta(hours=24)
                ).order_by('created_at').first()
                
                if first_response:
                    response_time = (first_response.created_at - msg.created_at).total_seconds()
                    response_times.append(response_time)
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
            
            variant_analytics.append({
                'variant_index': idx,
                'variant_name': variant.get('name', f'Variant {idx + 1}'),
                'content': variant.get('content', campaign.message_content),
                'customer_count': len(customer_ids),
                'delivered_count': delivered,
                'delivery_rate': round(delivery_rate, 2),
                'read_count': read,
                'read_rate': round(read_rate, 2),
                'response_count': response_count,
                'engagement_rate': round(engagement_rate, 2),
                'avg_response_time_seconds': round(avg_response_time, 2) if avg_response_time else None
            })
        
        # Add statistical comparison if we have 2 variants
        if len(variant_analytics) == 2:
            variant_analytics = self._add_statistical_comparison(variant_analytics)
        
        return variant_analytics
    
    def _add_statistical_comparison(self, variant_analytics: List[Dict]) -> List[Dict]:
        """
        Add statistical significance comparison between two variants.
        
        Uses a simple z-test for proportions to determine if the difference
        in engagement rates is statistically significant.
        
        Args:
            variant_analytics: List of exactly 2 variant analytics dicts
            
        Returns:
            Updated variant_analytics with statistical comparison
        """
        if len(variant_analytics) != 2:
            return variant_analytics
        
        v1 = variant_analytics[0]
        v2 = variant_analytics[1]
        
        # Calculate pooled proportion for z-test
        n1 = v1['delivered_count']
        n2 = v2['delivered_count']
        p1 = v1['engagement_rate'] / 100
        p2 = v2['engagement_rate'] / 100
        
        if n1 > 0 and n2 > 0:
            # Pooled proportion
            p_pool = ((p1 * n1) + (p2 * n2)) / (n1 + n2)
            
            # Standard error
            se = ((p_pool * (1 - p_pool)) * ((1/n1) + (1/n2))) ** 0.5
            
            # Z-score
            if se > 0:
                z_score = (p1 - p2) / se
                
                # Determine significance (using |z| > 1.96 for 95% confidence)
                is_significant = abs(z_score) > 1.96
                
                # Determine winner
                if is_significant:
                    winner = 'variant_0' if p1 > p2 else 'variant_1'
                    improvement = abs(p1 - p2) * 100
                else:
                    winner = None
                    improvement = 0
                
                # Add comparison to both variants
                comparison = {
                    'z_score': round(z_score, 3),
                    'is_significant': is_significant,
                    'confidence_level': '95%',
                    'winner': winner,
                    'improvement_percentage': round(improvement, 2)
                }
                
                variant_analytics[0]['statistical_comparison'] = comparison
                variant_analytics[1]['statistical_comparison'] = comparison
        
        return variant_analytics
