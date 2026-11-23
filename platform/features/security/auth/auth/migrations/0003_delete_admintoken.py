from django.db import migrations


class Migration(migrations.Migration):
    """Drop the legacy admin_tokens table and remove AdminToken from state.

    Uses `DROP TABLE IF EXISTS` so the migration is safe both for fresh
    databases (where the table never existed) and for upgraded databases
    inherited from the old 'administration' app.
    """

    dependencies = [
        ('platform_auth', '0002_add_ip_and_ua_to_admin_token'),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS admin_tokens CASCADE;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AdminToken'),
            ],
            database_operations=[],
        ),
    ]
