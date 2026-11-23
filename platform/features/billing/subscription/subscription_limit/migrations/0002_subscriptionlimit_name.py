from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_limit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionlimit',
            name='name',
            field=models.CharField(blank=True, default='', max_length=150, verbose_name='Nombre del tope'),
        ),
    ]
