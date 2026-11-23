# Generated manually — schema-only unique default currency per country.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geography_currency', '0001_currency_and_country_currency'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='countrycurrency',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True)),
                fields=('country',),
                name='uq_geography_country_one_default_currency',
            ),
        ),
    ]
