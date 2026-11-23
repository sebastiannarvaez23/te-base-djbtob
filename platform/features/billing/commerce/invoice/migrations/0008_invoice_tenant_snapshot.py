from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0007_alter_invoice_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='tenant_nit',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='NIT al emitir'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='tenant_name',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Razón social al emitir'),
        ),
    ]
