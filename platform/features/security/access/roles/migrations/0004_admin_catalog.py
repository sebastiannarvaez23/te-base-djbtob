import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Admin catalog tables (sections / modules / features) + rol_features FK.

    Schema-only — no data inserts or updates.
    """

    dependencies = [
        ('platform_roles', '0003_rename_admin_rol_features_modules'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='adminrolefeature',
            name='feature',
        ),
        migrations.CreateModel(
            name='AdminSection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Sección de administrador',
                'verbose_name_plural': 'Secciones de administrador',
                'db_table': 'admin_sections',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='AdminModule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=100, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('description', models.CharField(blank=True, default='', max_length=500, verbose_name='Descripción')),
                ('icon', models.CharField(max_length=100, verbose_name='Icono')),
                ('route', models.CharField(max_length=255, verbose_name='Ruta')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('section', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='modules',
                    to='platform_roles.adminsection',
                    verbose_name='Sección',
                )),
            ],
            options={
                'verbose_name': 'Módulo de administrador',
                'verbose_name_plural': 'Módulos de administrador',
                'db_table': 'admin_modules',
                'ordering': ['section__order', 'order'],
            },
        ),
        migrations.CreateModel(
            name='AdminFeature',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.CharField(max_length=100, unique=True, verbose_name='Clave')),
                ('label', models.CharField(max_length=200, verbose_name='Etiqueta')),
                ('category', models.CharField(default='features', max_length=50, verbose_name='Categoría')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('module', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='features',
                    to='platform_roles.adminmodule',
                    verbose_name='Módulo',
                )),
            ],
            options={
                'verbose_name': 'Feature de administrador',
                'verbose_name_plural': 'Features de administrador',
                'db_table': 'admin_features',
                'ordering': ['module__order', 'key'],
            },
        ),
        migrations.AddField(
            model_name='adminrolefeature',
            name='feature',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='rol_features',
                to='platform_roles.adminfeature',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='adminrolefeature',
            unique_together={('rol', 'feature')},
        ),
    ]
