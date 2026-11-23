import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('company', '0002_domain_uuid_pk'),
        ('subscription', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('invoice_number', models.CharField(max_length=50, unique=True, verbose_name='Número de factura')),
                ('issue_date', models.DateField(verbose_name='Fecha de emisión')),
                ('due_date', models.DateField(verbose_name='Fecha de vencimiento')),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Monto total')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pendiente'),
                        ('paid', 'Pagada'),
                        ('cancelled', 'Cancelada'),
                        ('overdue', 'Vencida'),
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Estado',
                )),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='invoices',
                    to='company.company',
                    verbose_name='Empresa',
                )),
                ('subscription', models.ForeignKey(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='invoices',
                    to='subscription.subscription',
                    verbose_name='Suscripción',
                )),
            ],
            options={
                'verbose_name': 'Factura',
                'verbose_name_plural': 'Facturas',
                'ordering': ['-issue_date'],
            },
        ),
    ]
