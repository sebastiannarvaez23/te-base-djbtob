from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_alter_charge_id_alter_chargeattempt_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='charge',
            name='tenant_nit',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='NIT al cobrar'),
        ),
        migrations.AddField(
            model_name='charge',
            name='tenant_name',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Razón social al cobrar'),
        ),
    ]
