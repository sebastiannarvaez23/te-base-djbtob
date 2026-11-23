from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_audit', '0003_auditlog_audit_logs_entity__d4c2e5_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='auditlog',
                    name='user_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de usuario'),
                ),
                migrations.AlterField(
                    model_name='auditlog',
                    name='warehouse_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de warehouse'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE audit_logs '
                        'ALTER COLUMN user_id TYPE uuid USING NULL::uuid, '
                        'ALTER COLUMN warehouse_id TYPE uuid USING NULL::uuid'
                    ),
                    reverse_sql=(
                        'ALTER TABLE audit_logs '
                        'ALTER COLUMN user_id TYPE integer USING NULL::integer, '
                        'ALTER COLUMN warehouse_id TYPE integer USING NULL::integer'
                    ),
                ),
            ],
        ),
    ]
