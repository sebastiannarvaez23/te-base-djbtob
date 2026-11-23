from django.db import migrations, models


class Migration(migrations.Migration):
    """No-op in fresh databases.

    Originally added `ip_address` and `user_agent` columns to the
    `admin_tokens` table (owned previously by the old 'administration'
    app). In fresh installations the table does not exist, so we only
    update Django state; 0003 will then remove the model entirely.
    """

    dependencies = [
        ('platform_auth', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='admintoken',
                    name='ip_address',
                    field=models.GenericIPAddressField(blank=True, null=True, verbose_name='Dirección IP'),
                ),
                migrations.AddField(
                    model_name='admintoken',
                    name='user_agent',
                    field=models.CharField(blank=True, default='', max_length=512, verbose_name='User-Agent'),
                ),
            ],
            database_operations=[],
        ),
    ]
