from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0013_subscription_currency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='currency',
            field=models.CharField(
                default='USD',
                help_text='ISO 4217 uppercase (e.g. USD, COP). Mirrored from the catalog service.',
                max_length=3,
                verbose_name='Currency (ISO 4217)',
            ),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='price',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Monthly list price mirrored from the linked Neurana catalog service.',
                max_digits=14,
                verbose_name='Precio',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='catalog_service_id',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text='Neurana catalog service that owns this plan price.',
                null=True,
                verbose_name='Servicio de catálogo',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='catalog_service_code',
            field=models.CharField(
                blank=True,
                default='',
                max_length=64,
                verbose_name='Código del servicio',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='catalog_service_name',
            field=models.CharField(
                blank=True,
                default='',
                max_length=255,
                verbose_name='Nombre del servicio',
            ),
        ),
        migrations.AlterField(
            model_name='companysubscription',
            name='price_paid',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                verbose_name='Precio pagado',
            ),
        ),
    ]
