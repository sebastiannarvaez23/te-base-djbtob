import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Sección',
                'verbose_name_plural': 'Secciones',
                'db_table': 'security_sections',
                'ordering': ['order'],
            },
        ),
    ]
