"""
Add payment preferences to Customer model.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0005_add_tenant_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='payment_preferences',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Customer payment preferences: {preferred_provider, saved_methods: [{provider, details}]}'
            ),
        ),
    ]
