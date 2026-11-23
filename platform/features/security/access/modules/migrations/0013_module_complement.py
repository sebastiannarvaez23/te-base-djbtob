from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0012_alter_module_id_alter_module_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='offering',
            field=models.CharField(
                choices=[('plan', 'Plan'), ('complement', 'Complemento')],
                default='plan',
                max_length=20,
                verbose_name='Contratación',
            ),
        ),
        migrations.AddField(
            model_name='module',
            name='billing_mode',
            field=models.CharField(
                choices=[
                    ('included', 'Incluida en el plan'),
                    ('renewal', 'Se adiciona a la suscripción'),
                    ('one_time', 'Pago de una sola vez'),
                ],
                default='included',
                max_length=20,
                verbose_name='Forma de cobro',
            ),
        ),
        migrations.AddField(
            model_name='module',
            name='catalog_service_id',
            field=models.UUIDField(blank=True, null=True, verbose_name='Servicio de catálogo'),
        ),
    ]
