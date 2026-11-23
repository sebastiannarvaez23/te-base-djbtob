from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('functionalities', '0006_alter_functionality_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='functionality',
            name='offering',
            field=models.CharField(
                choices=[('plan', 'Plan'), ('complement', 'Complemento')],
                default='plan',
                max_length=20,
                verbose_name='Contratación',
            ),
        ),
        migrations.AddField(
            model_name='functionality',
            name='billing_mode',
            field=models.CharField(
                choices=[
                    ('included', 'Incluida en el plan'),
                    ('renewal', 'Renovación'),
                    ('one_time', 'Adquisición única'),
                ],
                default='included',
                max_length=20,
                verbose_name='Modalidad',
            ),
        ),
        migrations.AddField(
            model_name='functionality',
            name='catalog_service_id',
            field=models.UUIDField(blank=True, null=True, verbose_name='Servicio de catálogo'),
        ),
    ]
