from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_filters', '0003_alter_modulefilter_module_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modulefilter',
            name='module_key',
            field=models.CharField(
                choices=[
                    ('warehouse', 'warehouse'),
                    ('receiving.receipts', 'receiving.receipts'),
                    ('receiving.putaway', 'receiving.putaway'),
                ],
                max_length=40,
            ),
        ),
    ]
