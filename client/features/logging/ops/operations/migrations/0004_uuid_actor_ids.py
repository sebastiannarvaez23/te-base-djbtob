from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_operations', '0003_alter_warehouseevent_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='warehouseevent',
                    name='user_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de usuario'),
                ),
                migrations.AlterField(
                    model_name='warehouseevent',
                    name='warehouse_id',
                    field=models.UUIDField(blank=True, null=True, verbose_name='ID de warehouse'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE warehouse_events '
                        'ALTER COLUMN user_id TYPE uuid USING NULL::uuid, '
                        'ALTER COLUMN warehouse_id TYPE uuid USING NULL::uuid'
                    ),
                    reverse_sql=(
                        'ALTER TABLE warehouse_events '
                        'ALTER COLUMN user_id TYPE integer USING NULL::integer, '
                        'ALTER COLUMN warehouse_id TYPE integer USING NULL::integer'
                    ),
                ),
            ],
        ),
    ]
