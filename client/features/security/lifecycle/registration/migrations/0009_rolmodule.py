import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0008_company_rol_access'),
    ]

    operations = [
        migrations.CreateModel(
            name='RolModule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module_code', models.CharField(max_length=100, verbose_name='Código del módulo')),
                ('rol', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rol_modules',
                    to='registration.rol',
                )),
            ],
            options={
                'db_table': 'security_rol_modules',
                'unique_together': {('rol', 'module_code')},
            },
        ),
    ]
