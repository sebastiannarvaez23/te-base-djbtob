from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0010_company_lifecycle'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='export_attested_by',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='export_object_key',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='company',
            name='users_tombstoned',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='company',
            name='lifecycle',
            field=models.CharField(
                choices=[
                    ('ACTIVE', 'Active'),
                    ('CLOSED', 'Closed'),
                    ('PENDING_PURGE', 'Pending purge'),
                    ('GONE', 'Gone'),
                ],
                default='ACTIVE',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='closedtenantrecord',
            name='users_tombstoned',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='closedtenantrecord',
            name='schema_dropped',
            field=models.BooleanField(default=False),
        ),
    ]
