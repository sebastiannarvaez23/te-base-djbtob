import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0006_company_geo_city'),
        ('geography_location', '0001_initial_and_geo_country_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='company',
            name='geo_city',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='companies',
                to='geography_location.city',
            ),
        ),
        migrations.RemoveField(
            model_name='company',
            name='country',
        ),
        migrations.RemoveField(
            model_name='company',
            name='state',
        ),
        migrations.RemoveField(
            model_name='company',
            name='city',
        ),
    ]
