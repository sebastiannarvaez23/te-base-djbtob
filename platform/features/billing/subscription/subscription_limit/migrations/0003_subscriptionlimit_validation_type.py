from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_limit', '0002_subscriptionlimit_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionlimit',
            name='validation_type',
            field=models.CharField(
                choices=[('daily', 'Diario'), ('lifetime', 'Por suscripción')],
                default='lifetime',
                max_length=20,
                verbose_name='Tipo de validación',
            ),
        ),
    ]
