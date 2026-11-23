from django.db import migrations


class Migration(migrations.Migration):
    """Rename catalog table to ``security_features`` (schema-only)."""

    dependencies = [
        ('functionalities', '0004_alter_functionality_key_alter_functionality_label'),
        ('registration', '0010_consolidate_features'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='functionality',
            table='security_features',
        ),
    ]
