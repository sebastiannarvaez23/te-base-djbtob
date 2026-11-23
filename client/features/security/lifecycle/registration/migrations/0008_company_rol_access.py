from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0007_rol_company'),
        ('company', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyRolAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rol_accesses',
                    to='company.company',
                    verbose_name='Empresa',
                )),
                ('rol', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='company_accesses',
                    to='registration.rol',
                    verbose_name='Rol',
                )),
            ],
            options={
                'db_table': 'security_company_rol_access',
                'unique_together': {('company', 'rol')},
            },
        ),
    ]
