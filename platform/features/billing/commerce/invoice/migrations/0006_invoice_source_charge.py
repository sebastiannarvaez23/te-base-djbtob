from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0005_invoice_company_subscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='source_charge_id',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Cobro origen',
            ),
        ),
    ]
