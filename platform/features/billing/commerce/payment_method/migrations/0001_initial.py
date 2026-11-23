import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('company', '0002_domain_uuid_pk'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('provider', models.CharField(max_length=100, verbose_name='Proveedor')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_methods',
                    to='company.company',
                    verbose_name='Empresa',
                )),
            ],
            options={
                'verbose_name': 'Método de pago',
                'verbose_name_plural': 'Métodos de pago',
            },
        ),
    ]
