import core.ids
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0010_invoice_fiscal_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='NeuranaWebhookInbox',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('external_event_id', models.CharField(max_length=128, unique=True)),
                ('event_type', models.CharField(blank=True, default='', max_length=100)),
                ('payload', models.JSONField(default=dict)),
                ('signature', models.CharField(blank=True, default='', max_length=512)),
                ('signature_verified', models.BooleanField(default=False)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('processing_error', models.CharField(blank=True, default='', max_length=512)),
                ('invoice', models.ForeignKey(
                    blank=True,
                    db_constraint=False,
                    null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='neurana_webhook_events',
                    to='invoice.invoice',
                )),
            ],
            options={
                'db_table': 'billing_neurana_webhook_inbox',
                'ordering': ['-received_at'],
            },
        ),
        migrations.AddIndex(
            model_name='neuranawebhookinbox',
            index=models.Index(fields=['processed_at'], name='idx_ne_inbox_processed'),
        ),
    ]
