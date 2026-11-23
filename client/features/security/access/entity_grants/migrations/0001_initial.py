import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EntityGrant',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.UUIDField()),
                ('entity_type', models.CharField(choices=[('warehouse', 'warehouse')], max_length=32)),
                ('entity_id', models.UUIDField()),
                ('granted_by', models.UUIDField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'security_entity_grants',
                'indexes': [models.Index(fields=['entity_type', 'entity_id'], name='egrant_entity_idx')],
            },
        ),
        migrations.AddConstraint(
            model_name='entitygrant',
            constraint=models.UniqueConstraint(fields=('user_id', 'entity_type', 'entity_id'), name='egrant_user_entity_uniq'),
        ),
    ]
