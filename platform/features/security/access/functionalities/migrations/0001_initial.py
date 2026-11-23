import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('modules', '0009_update_orders_route'),
    ]

    operations = [
        migrations.CreateModel(
            name='Functionality',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('code', models.CharField(max_length=100, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('description', models.CharField(blank=True, max_length=500, verbose_name='Descripción')),
                ('module', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='functionalities',
                    to='modules.module',
                    verbose_name='Módulo',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Funcionalidad',
                'verbose_name_plural': 'Funcionalidades',
                'db_table': 'security_functionalities',
                'ordering': ['module__order', 'code'],
            },
        ),
    ]
