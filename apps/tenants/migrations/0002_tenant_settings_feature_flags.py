# Generated migration for tenant settings feature flags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantsettings',
            name='feature_flags',
            field=models.JSONField(blank=True, default=dict, help_text='Feature flags for gradual rollout and A/B testing'),
        ),
    ]
