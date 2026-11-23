import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('platform_roles', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminUser',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=150, unique=True, verbose_name='Usuario')),
                ('email', models.EmailField(unique=True, verbose_name='Correo electrónico')),
                ('first_name', models.CharField(max_length=100, verbose_name='Nombre')),
                ('last_name', models.CharField(max_length=100, verbose_name='Apellido')),
                ('password', models.CharField(max_length=128, verbose_name='Contraseña')),
                ('role', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='users',
                    to='platform_roles.adminrole',
                    verbose_name='Rol',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('is_superuser', models.BooleanField(default=False, verbose_name='Superusuario')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='Último acceso')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Usuario administrador',
                'verbose_name_plural': 'Usuarios administradores',
                'db_table': 'admin_users',
            },
        ),
    ]
