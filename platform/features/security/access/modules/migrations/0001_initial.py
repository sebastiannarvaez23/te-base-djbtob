import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('code', models.CharField(max_length=100, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('description', models.CharField(blank=True, max_length=500, verbose_name='Descripción')),
                ('icon', models.CharField(max_length=100, verbose_name='Icono')),
                ('route', models.CharField(max_length=255, verbose_name='Ruta')),
                ('section', models.CharField(
                    choices=[
                        ('none',        'General'),
                        ('operational', 'Operativo'),
                        ('management',  'Gestión'),
                        ('analytics',   'Analítica y Control'),
                        ('system',      'Sistema'),
                    ],
                    default='none',
                    max_length=20,
                    verbose_name='Sección',
                )),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Módulo',
                'verbose_name_plural': 'Módulos',
                'db_table': 'security_modules',
                'ordering': ['section', 'order'],
            },
        ),
    ]
