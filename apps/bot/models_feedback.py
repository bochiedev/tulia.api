"""
Feedback collection models for continuous learning.

Tracks user feedback, implicit signals, and human corrections.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel, BaseModelManager


class InteractionFeedbackManager(BaseModelManager):
    """Manager for interaction feedback queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get feedback for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def positive_feedback(self, tenant):
        """Get positive feedback for a tenant."""
        return self.filter(tenant=tenant, rating='helpful')
    
    def negative_feedback(self, tenant):
        """Get negative feedback for a tenant."""
        return self.filter(tenant=tenant, rating='not_helpful')
    
    def with_comments(self, tenant):
        """Get feedback with text comments."""
        return self.filter(tenant=tenant).exclude(feedback_text='')


class InteractionFeedback(BaseModel):
    """
    User feedback on bot interactions.
    
    Captures:
    - Thumbs up/down ratings
    - Optional text feedback
    - Implicit engagement signals
    - Response time tracking
    
    TENANT SCOPING: All queries MUST filter by tenant.
    """
    
    RATING_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='interaction_feedback',
        db_index=True,
        help_text="Tenant this feedback belongs to"
    )
    
    agent_interaction = models.ForeignKey(
        'bot.AgentInteraction',
        on_delete=models.CASCADE,
        related_name='feedback',
        help_text="Agent interaction being rated"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='interaction_feedback',
        help_text="Conversation this feedback belongs to"
    )
    
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='interaction_feedback',
        help_text="Customer who provided feedback"
    )
    
    # Explicit Feedback
    rating = models.CharField(
        max_length=20,
        choices=RATING_CHOICES,
        db_index=True,
        help_text="User rating (helpful/not_helpful)"
    )
    
    feedback_text = models.TextField(
        blank=True,
        help_text="Optional text feedback from user"
    )
    
    # Implicit Signals
    user_continued = models.BooleanField(
        default=False,
        help_text="User continued conversation after bot response"
    )
    
    completed_action = models.BooleanField(
        default=False,
        help_text="User completed intended action (purchase, booking, etc.)"
    )
    
    requested_human = models.BooleanField(
        default=False,
        help_text="User requested human handoff"
    )
    
    response_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken for user to respond (engagement metric)"
    )
    
    # Metadata
    feedback_source = models.CharField(
        max_length=50,
        default='whatsapp_button',
        help_text="Source of feedback (whatsapp_button, api, etc.)"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional feedback metadata"
    )
    
    objects = InteractionFeedbackManager()
    
    class Meta:
        db_table = 'bot_interaction_feedback'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'rating', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.customer} - {self.rating} - {self.created_at}"
    
    @property
    def implicit_satisfaction_score(self) -> float:
        """
        Calculate implicit satisfaction score (0.0 to 1.0).
        
        Based on behavioral signals:
        - User continued: +0.3
        - Completed action: +0.5
        - Requested human: -0.5
        - Fast response (<30s): +0.2
        """
        score = 0.5  # Neutral baseline
        
        if self.user_continued:
            score += 0.3
        
        if self.completed_action:
            score += 0.5
        
        if self.requested_human:
            score -= 0.5
        
        if self.response_time_seconds and self.response_time_seconds < 30:
            score += 0.2
        
        # Clamp to 0.0-1.0
        return max(0.0, min(1.0, score))


class HumanCorrectionManager(BaseModelManager):
    """Manager for human correction queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get corrections for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def approved_for_training(self, tenant):
        """Get corrections approved for training."""
        return self.filter(tenant=tenant, approved_for_training=True)
    
    def by_category(self, tenant, category):
        """Get corrections by category."""
        return self.filter(tenant=tenant, correction_category=category)


class HumanCorrection(BaseModel):
    """
    Human agent corrections to bot responses.
    
    Captures:
    - Bot's original response
    - Human agent's corrected response
    - Correction reason and category
    - Training approval status
    
    TENANT SCOPING: All queries MUST filter by tenant.
    """
    
    CATEGORY_CHOICES = [
        ('factual_error', 'Factual Error'),
        ('tone_inappropriate', 'Inappropriate Tone'),
        ('missing_information', 'Missing Information'),
        ('wrong_intent', 'Wrong Intent Detection'),
        ('poor_recommendation', 'Poor Recommendation'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='human_corrections',
        db_index=True,
        help_text="Tenant this correction belongs to"
    )
    
    agent_interaction = models.ForeignKey(
        'bot.AgentInteraction',
        on_delete=models.CASCADE,
        related_name='human_corrections',
        help_text="Agent interaction that was corrected"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='human_corrections',
        help_text="Conversation this correction belongs to"
    )
    
    # Original Bot Response
    bot_response = models.TextField(
        help_text="Original bot response that was incorrect"
    )
    
    # Human Correction
    human_response = models.TextField(
        help_text="Corrected response from human agent"
    )
    
    correction_reason = models.TextField(
        help_text="Explanation of why correction was needed"
    )
    
    correction_category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        db_index=True,
        help_text="Category of correction"
    )
    
    # Human Agent Info
    corrected_by = models.ForeignKey(
        'rbac.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bot_corrections',
        help_text="Human agent who made the correction"
    )
    
    # Training Approval
    approved_for_training = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this correction is approved for training data"
    )
    
    approved_by = models.ForeignKey(
        'rbac.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_corrections',
        help_text="User who approved this correction for training"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this correction was approved"
    )
    
    # Quality Score
    quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Quality rating of the correction (0-5)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional correction metadata"
    )
    
    objects = HumanCorrectionManager()
    
    class Meta:
        db_table = 'bot_human_correction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'approved_for_training', 'created_at']),
            models.Index(fields=['tenant', 'correction_category', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"Correction for {self.agent_interaction} - {self.correction_category}"
