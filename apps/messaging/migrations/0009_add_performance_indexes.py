# Generated migration for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0008_add_input_length_limits'),
    ]

    operations = [
        # Add composite index for conversation history queries
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['conversation', 'created_at', 'direction'],
                name='msg_conv_created_dir_idx'
            ),
        ),
        # Add index for message type filtering
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['conversation', 'message_type', 'created_at'],
                name='msg_conv_type_created_idx'
            ),
        ),
        # Add index for conversation status queries
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(
                fields=['tenant', 'status', 'updated_at'],
                name='conv_tenant_status_upd_idx'
            ),
        ),
    ]
