import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Claims ownership of the existing admin_tokens table (previously owned by
    the 'administration' app). Uses SeparateDatabaseAndState so no DDL is
    executed — the table already exists in the database.
    """

    initial = True
    dependencies = [
        ('platform_users', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='AdminToken',
                    fields=[
                        ('key', models.CharField(max_length=40, primary_key=True, serialize=False)),
                        ('user', models.OneToOneField(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='auth_token',
                            to='platform_users.adminuser',
                            verbose_name='Usuario administrador',
                        )),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                    ],
                    options={
                        'verbose_name': 'Token de administrador',
                        'verbose_name_plural': 'Tokens de administrador',
                        'db_table': 'admin_tokens',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
