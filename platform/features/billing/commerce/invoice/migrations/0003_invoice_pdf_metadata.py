from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0002_alter_invoice_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='pdf_bucket',
            field=models.CharField(
                blank=True, default='', max_length=120, verbose_name='Bucket del PDF',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='pdf_object_key',
            field=models.CharField(
                blank=True, default='', max_length=500, verbose_name='Object key del PDF',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='pdf_sent_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Enviado al cliente en',
            ),
        ),
    ]
