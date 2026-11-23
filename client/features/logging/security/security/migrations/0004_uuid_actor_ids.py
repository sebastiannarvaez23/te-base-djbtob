from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_security', '0003_securitylog_security_lo_event_t_25aa39_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='securitylog',
                    name='user_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de usuario'),
                ),
                migrations.AlterField(
                    model_name='securitylog',
                    name='target_user_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de usuario objetivo'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE security_logs '
                        'ALTER COLUMN user_id TYPE uuid USING NULL::uuid, '
                        'ALTER COLUMN target_user_id TYPE uuid USING NULL::uuid'
                    ),
                    reverse_sql=(
                        'ALTER TABLE security_logs '
                        'ALTER COLUMN user_id TYPE integer USING NULL::integer, '
                        'ALTER COLUMN target_user_id TYPE integer USING NULL::integer'
                    ),
                ),
            ],
        ),
    ]
