import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreferences',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('language', models.CharField(
                    choices=[('es', 'Español'), ('en', 'English'), ('pt', 'Português'), ('fr', 'Français')],
                    default='es',
                    max_length=5,
                    verbose_name='Idioma',
                )),
                ('theme', models.CharField(
                    choices=[('light', 'Claro'), ('dark', 'Oscuro'), ('system', 'Sistema')],
                    default='light',
                    max_length=10,
                    verbose_name='Tema',
                )),
                ('timezone', models.CharField(
                    default='America/Bogota',
                    max_length=60,
                    verbose_name='Zona horaria',
                )),
                ('date_format', models.CharField(
                    choices=[('DD/MM/YYYY', 'DD/MM/YYYY'), ('MM/DD/YYYY', 'MM/DD/YYYY'), ('YYYY-MM-DD', 'YYYY-MM-DD')],
                    default='DD/MM/YYYY',
                    max_length=12,
                    verbose_name='Formato de fecha',
                )),
                ('sidebar_collapsed', models.BooleanField(default=False, verbose_name='Barra lateral contraída')),
                ('items_per_page', models.PositiveSmallIntegerField(default=20, verbose_name='Elementos por página')),
                ('notifications_enabled', models.BooleanField(default=True, verbose_name='Notificaciones activas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preferences',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario',
                )),
            ],
            options={
                'verbose_name': 'Preferencias de usuario',
                'verbose_name_plural': 'Preferencias de usuarios',
            },
        ),
    ]
