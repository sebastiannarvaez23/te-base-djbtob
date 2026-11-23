from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0003_alter_rol_table_alter_user_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(max_length=100, verbose_name='Módulo')),
                ('key', models.CharField(max_length=200, unique=True, verbose_name='Clave')),
                ('label', models.CharField(max_length=200, verbose_name='Etiqueta')),
                ('category', models.CharField(default='features', max_length=50, verbose_name='Categoría')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'db_table': 'security_features',
                'ordering': ['module', 'key'],
            },
        ),
        migrations.CreateModel(
            name='RolFeature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rol_features', to='registration.rol')),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rol_features', to='registration.feature')),
            ],
            options={
                'db_table': 'security_rol_features',
                'unique_together': {('rol', 'feature')},
            },
        ),
    ]
