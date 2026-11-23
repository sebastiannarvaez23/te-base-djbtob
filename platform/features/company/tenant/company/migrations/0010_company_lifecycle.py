import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0009_alter_company_nit_company_uniq_company_nit_when_set'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='lifecycle',
            field=models.CharField(
                choices=[
                    ('ACTIVE', 'Active'),
                    ('CLOSED', 'Closed'),
                    ('PENDING_PURGE', 'Pending purge'),
                ],
                default='ACTIVE',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='purge_after',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='closed_reason',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='company',
            name='closed_by_admin_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='legal_hold',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='company',
            name='legal_hold_reason',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='company',
            name='export_attested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['lifecycle', 'purge_after'], name='idx_companies_lifecycle_purge'),
        ),
        migrations.CreateModel(
            name='ClosedTenantRecord',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('company_id', models.UUIDField(unique=True)),
                ('nit', models.CharField(blank=True, default='', max_length=40)),
                ('name', models.CharField(max_length=200)),
                ('schema_name', models.CharField(max_length=63)),
                ('closed_at', models.DateTimeField()),
                ('purged_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'closed_tenant_records',
            },
        ),
    ]
