# Generated migration for provider tracking models

from django.db import migrations, models
import django.core.validators
from decimal import Decimal
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0011_add_rag_config_fields'),
        ('tenants', '0001_initial'),
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProviderUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('provider', models.CharField(db_index=True, help_text='Provider name (openai, gemini, together)', max_length=50)),
                ('model', models.CharField(db_index=True, help_text='Model name (gpt-4o, gemini-1.5-pro, etc.)', max_length=100)),
                ('input_tokens', models.IntegerField(help_text='Number of input tokens', validators=[django.core.validators.MinValueValidator(0)])),
                ('output_tokens', models.IntegerField(help_text='Number of output tokens', validators=[django.core.validators.MinValueValidator(0)])),
                ('total_tokens', models.IntegerField(help_text='Total tokens (input + output)', validators=[django.core.validators.MinValueValidator(0)])),
                ('estimated_cost', models.DecimalField(decimal_places=6, help_text='Estimated cost in USD', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('latency_ms', models.IntegerField(help_text='API call latency in milliseconds', validators=[django.core.validators.MinValueValidator(0)])),
                ('success', models.BooleanField(default=True, help_text='Whether the API call succeeded')),
                ('error_message', models.TextField(blank=True, help_text='Error message if call failed')),
                ('finish_reason', models.CharField(blank=True, help_text='Finish reason (stop, length, safety, etc.)', max_length=50)),
                ('was_failover', models.BooleanField(default=False, help_text='Whether this was a failover attempt')),
                ('routing_reason', models.CharField(blank=True, help_text='Reason for provider/model selection', max_length=200)),
                ('complexity_score', models.FloatField(blank=True, help_text='Complexity score that influenced routing', null=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional provider-specific metadata')),
                ('agent_interaction', models.ForeignKey(blank=True, help_text='Agent interaction this usage is associated with', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='provider_usage', to='bot.agentinteraction')),
                ('conversation', models.ForeignKey(blank=True, help_text='Conversation this usage is associated with', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='provider_usage', to='messaging.conversation')),
                ('tenant', models.ForeignKey(db_index=True, help_text='Tenant this usage belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='provider_usage', to='tenants.tenant')),
            ],
            options={
                'db_table': 'bot_provider_usage',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProviderDailySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('date', models.DateField(db_index=True, help_text='Date of this summary')),
                ('provider', models.CharField(db_index=True, help_text='Provider name', max_length=50)),
                ('model', models.CharField(db_index=True, help_text='Model name', max_length=100)),
                ('total_calls', models.IntegerField(default=0, help_text='Total number of API calls', validators=[django.core.validators.MinValueValidator(0)])),
                ('successful_calls', models.IntegerField(default=0, help_text='Number of successful calls', validators=[django.core.validators.MinValueValidator(0)])),
                ('failed_calls', models.IntegerField(default=0, help_text='Number of failed calls', validators=[django.core.validators.MinValueValidator(0)])),
                ('total_input_tokens', models.BigIntegerField(default=0, help_text='Total input tokens', validators=[django.core.validators.MinValueValidator(0)])),
                ('total_output_tokens', models.BigIntegerField(default=0, help_text='Total output tokens', validators=[django.core.validators.MinValueValidator(0)])),
                ('total_tokens', models.BigIntegerField(default=0, help_text='Total tokens', validators=[django.core.validators.MinValueValidator(0)])),
                ('total_cost', models.DecimalField(decimal_places=6, default=Decimal('0'), help_text='Total cost in USD', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('avg_latency_ms', models.FloatField(blank=True, help_text='Average latency in milliseconds', null=True)),
                ('p50_latency_ms', models.IntegerField(blank=True, help_text='50th percentile latency', null=True)),
                ('p95_latency_ms', models.IntegerField(blank=True, help_text='95th percentile latency', null=True)),
                ('p99_latency_ms', models.IntegerField(blank=True, help_text='99th percentile latency', null=True)),
                ('failover_count', models.IntegerField(default=0, help_text='Number of failover attempts', validators=[django.core.validators.MinValueValidator(0)])),
                ('tenant', models.ForeignKey(db_index=True, help_text='Tenant this summary belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='provider_daily_summaries', to='tenants.tenant')),
            ],
            options={
                'db_table': 'bot_provider_daily_summary',
                'ordering': ['-date', 'provider', 'model'],
            },
        ),
        migrations.AddIndex(
            model_name='providerusage',
            index=models.Index(fields=['tenant', 'created_at'], name='bot_provide_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='providerusage',
            index=models.Index(fields=['tenant', 'provider', 'created_at'], name='bot_provide_tenant__provider_idx'),
        ),
        migrations.AddIndex(
            model_name='providerusage',
            index=models.Index(fields=['tenant', 'model', 'created_at'], name='bot_provide_tenant__model_idx'),
        ),
        migrations.AddIndex(
            model_name='providerusage',
            index=models.Index(fields=['conversation', 'created_at'], name='bot_provide_convers_idx'),
        ),
        migrations.AddIndex(
            model_name='providerdailysummary',
            index=models.Index(fields=['tenant', 'date'], name='bot_provide_tenant__date_idx'),
        ),
        migrations.AddIndex(
            model_name='providerdailysummary',
            index=models.Index(fields=['tenant', 'provider', 'date'], name='bot_provide_tenant__provider_date_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='providerdailysummary',
            unique_together={('tenant', 'date', 'provider', 'model')},
        ),
    ]
