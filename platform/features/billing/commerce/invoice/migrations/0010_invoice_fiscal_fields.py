from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0009_invoice_company_set_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='external_id',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=64,
                verbose_name='Fiscal external id',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='fiscal_number',
            field=models.CharField(
                blank=True, default='', max_length=64, verbose_name='Fiscal number',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='fiscal_status',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=20,
                verbose_name='Fiscal status',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='fiscal_payload',
            field=models.JSONField(blank=True, default=dict, verbose_name='Fiscal payload'),
        ),
    ]
