import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0004_invoice_currency_metadata'),
        ('subscription', '0010_billingsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='company_subscription',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='period_invoices',
                to='subscription.companysubscription',
                verbose_name='Período de suscripción',
            ),
        ),
    ]
