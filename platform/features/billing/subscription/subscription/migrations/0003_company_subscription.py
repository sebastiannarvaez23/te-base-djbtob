import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0002_insert_subscriptions'),
        ('company', '0003_company_add_subscription'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanySubscription',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True,
                    serialize=False, verbose_name='Id',
                )),
                ('start_date', models.DateTimeField(verbose_name='Fecha de inicio')),
                ('end_date', models.DateTimeField(verbose_name='Fecha de vigencia')),
                ('status', models.CharField(
                    choices=[
                        ('active',    'Activa'),
                        ('cancelled', 'Cancelada'),
                        ('expired',   'Vencida'),
                        ('suspended', 'Suspendida'),
                    ],
                    default='active',
                    max_length=20,
                    verbose_name='Estado',
                )),
                ('price_paid', models.DecimalField(
                    decimal_places=2, max_digits=10, verbose_name='Precio pagado',
                )),
                ('auto_renew', models.BooleanField(default=True, verbose_name='Renovación automática')),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subscription_acquisitions',
                    to='company.company',
                    verbose_name='Empresa',
                )),
                ('subscription', models.ForeignKey(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='acquisitions',
                    to='subscription.subscription',
                    verbose_name='Plan',
                )),
            ],
            options={
                'verbose_name': 'Adquisición de suscripción',
                'verbose_name_plural': 'Adquisiciones de suscripción',
                'ordering': ['-start_date'],
            },
        ),
    ]
