from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_limit', '0003_subscriptionlimit_validation_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriptionlimit',
            name='validation_type',
            field=models.CharField(
                choices=[
                    ('daily', 'Diario'),
                    ('lifetime', 'Por suscripción'),
                    ('window', 'Por ventana'),
                ],
                default='lifetime',
                max_length=20,
                verbose_name='Tipo de validación',
            ),
        ),
        migrations.AddField(
            model_name='subscriptionlimit',
            name='window_hours',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Obligatorio si el tipo de validación es por ventana. Ejemplo: 3 horas × 3 usos.',
                null=True,
                verbose_name='Duración de la ventana (horas)',
            ),
        ),
    ]
