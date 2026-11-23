import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
        ('subscription', '0010_billingsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='charge',
            name='company_subscription',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='period_charges',
                to='subscription.companysubscription',
                verbose_name='Período de suscripción',
            ),
        ),
    ]
