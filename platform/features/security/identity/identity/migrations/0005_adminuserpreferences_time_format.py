from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platform_identity', '0004_alter_adminuserpreferences_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminuserpreferences',
            name='time_format',
            field=models.CharField(
                choices=[('24', '24'), ('12', '12')],
                default='24',
                max_length=2,
            ),
        ),
    ]
