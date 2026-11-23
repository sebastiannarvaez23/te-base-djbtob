import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0002_domain_uuid_pk'),
        ('subscription', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='subscription',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='companies',
                to='subscription.subscription',
                verbose_name='Suscripción',
            ),
        ),
    ]
