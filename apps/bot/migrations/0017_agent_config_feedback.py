# Generated migration for agent configuration feedback fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0016_feedback_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfiguration',
            name='enable_feedback_collection',
            field=models.BooleanField(default=True, help_text='Enable feedback collection buttons after bot responses'),
        ),
        migrations.AddField(
            model_name='agentconfiguration',
            name='feedback_frequency',
            field=models.CharField(
                choices=[('always', 'Always'), ('sometimes', 'Sometimes (every 3rd message)'), ('never', 'Never')],
                default='sometimes',
                help_text='How often to show feedback buttons',
                max_length=20
            ),
        ),
    ]
