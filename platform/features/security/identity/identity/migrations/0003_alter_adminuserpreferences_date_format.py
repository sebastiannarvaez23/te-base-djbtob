from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platform_identity', '0002_alter_adminuserpreferences_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminuserpreferences',
            name='date_format',
            field=models.CharField(
                choices=[
                    ('DD/MM/YYYY', 'DD/MM/YYYY'),
                    ('MM/DD/YYYY', 'MM/DD/YYYY'),
                    ('YYYY-MM-DD', 'YYYY-MM-DD'),
                ],
                default='DD/MM/YYYY',
                max_length=12,
            ),
        ),
    ]
