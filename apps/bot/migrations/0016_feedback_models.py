# Generated migration for feedback models

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0015_provider_tracking'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InteractionFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('rating', models.CharField(choices=[('helpful', 'Helpful'), ('not_helpful', 'Not Helpful')], db_index=True, help_text='User rating (helpful/not_helpful)', max_length=20)),
                ('feedback_text', models.TextField(blank=True, help_text='Optional text feedback from user')),
                ('user_continued', models.BooleanField(default=False, help_text='User continued conversation after bot response')),
                ('completed_action', models.BooleanField(default=False, help_text='User completed intended action (purchase, booking, etc.)')),
                ('requested_human', models.BooleanField(default=False, help_text='User requested human handoff')),
                ('response_time_seconds', models.IntegerField(blank=True, help_text='Time taken for user to respond (engagement metric)', null=True)),
                ('feedback_source', models.CharField(default='whatsapp_button', help_text='Source of feedback (whatsapp_button, api, etc.)', max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional feedback metadata')),
                ('agent_interaction', models.ForeignKey(help_text='Agent interaction being rated', on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='bot.agentinteraction')),
                ('conversation', models.ForeignKey(help_text='Conversation this feedback belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='interaction_feedback', to='messaging.conversation')),
                ('customer', models.ForeignKey(help_text='Customer who provided feedback', on_delete=django.db.models.deletion.CASCADE, related_name='interaction_feedback', to='tenants.customer')),
                ('tenant', models.ForeignKey(db_index=True, help_text='Tenant this feedback belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='interaction_feedback', to='tenants.tenant')),
            ],
            options={
                'db_table': 'bot_interaction_feedback',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HumanCorrection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('bot_response', models.TextField(help_text='Original bot response that was incorrect')),
                ('human_response', models.TextField(help_text='Corrected response from human agent')),
                ('correction_reason', models.TextField(help_text='Explanation of why correction was needed')),
                ('correction_category', models.CharField(choices=[('factual_error', 'Factual Error'), ('tone_inappropriate', 'Inappropriate Tone'), ('missing_information', 'Missing Information'), ('wrong_intent', 'Wrong Intent Detection'), ('poor_recommendation', 'Poor Recommendation'), ('other', 'Other')], db_index=True, help_text='Category of correction', max_length=50)),
                ('approved_for_training', models.BooleanField(db_index=True, default=False, help_text='Whether this correction is approved for training data')),
                ('approved_at', models.DateTimeField(blank=True, help_text='When this correction was approved', null=True)),
                ('quality_score', models.FloatField(blank=True, help_text='Quality rating of the correction (0-5)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(5.0)])),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional correction metadata')),
                ('agent_interaction', models.ForeignKey(help_text='Agent interaction that was corrected', on_delete=django.db.models.deletion.CASCADE, related_name='human_corrections', to='bot.agentinteraction')),
                ('approved_by', models.ForeignKey(blank=True, help_text='User who approved this correction for training', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_corrections', to=settings.AUTH_USER_MODEL)),
                ('conversation', models.ForeignKey(help_text='Conversation this correction belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='human_corrections', to='messaging.conversation')),
                ('corrected_by', models.ForeignKey(blank=True, help_text='Human agent who made the correction', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bot_corrections', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(db_index=True, help_text='Tenant this correction belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='human_corrections', to='tenants.tenant')),
            ],
            options={
                'db_table': 'bot_human_correction',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='interactionfeedback',
            index=models.Index(fields=['tenant', 'created_at'], name='bot_interac_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='interactionfeedback',
            index=models.Index(fields=['tenant', 'rating', 'created_at'], name='bot_interac_tenant__rating_idx'),
        ),
        migrations.AddIndex(
            model_name='interactionfeedback',
            index=models.Index(fields=['conversation', 'created_at'], name='bot_interac_convers_idx'),
        ),
        migrations.AddIndex(
            model_name='interactionfeedback',
            index=models.Index(fields=['customer', 'created_at'], name='bot_interac_custome_idx'),
        ),
        migrations.AddIndex(
            model_name='humancorrection',
            index=models.Index(fields=['tenant', 'created_at'], name='bot_humanc_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='humancorrection',
            index=models.Index(fields=['tenant', 'approved_for_training', 'created_at'], name='bot_humanc_tenant__approved_idx'),
        ),
        migrations.AddIndex(
            model_name='humancorrection',
            index=models.Index(fields=['tenant', 'correction_category', 'created_at'], name='bot_humanc_tenant__category_idx'),
        ),
        migrations.AddIndex(
            model_name='humancorrection',
            index=models.Index(fields=['conversation', 'created_at'], name='bot_humanc_convers_idx'),
        ),
    ]
