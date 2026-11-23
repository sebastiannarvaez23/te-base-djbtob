from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_operations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouseevent',
            name='company_subscription_id',
            field=models.UUIDField(
                blank=True, null=True, verbose_name='Período de suscripción',
            ),
        ),
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(
                fields=['company_subscription_id'],
                name='warehouse_e_company_idx',
            ),
        ),
    ]
