from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identity', '0003_alter_userpreferences_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreferences',
            name='time_format',
            field=models.CharField(
                choices=[('24', '24'), ('12', '12')],
                default='24',
                max_length=2,
                verbose_name='Formato de hora',
            ),
        ),
    ]
