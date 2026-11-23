from django.db import migrations

from core.migration_operations import EnsureModelTable


class Migration(migrations.Migration):

    dependencies = [
        ('logging_config', '0001_initial_state_uuid7'),
    ]

    operations = [
        EnsureModelTable('LogConfiguration'),
    ]
