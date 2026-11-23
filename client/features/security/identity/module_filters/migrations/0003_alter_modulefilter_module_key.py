from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_filters', '0002_name_ci_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modulefilter',
            name='module_key',
            field=models.CharField(
                choices=[('warehouse', 'warehouse')],
                max_length=40,
            ),
        ),
    ]
