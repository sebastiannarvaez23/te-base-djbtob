import uuid

from django.db import migrations, models
import django.db.models.deletion


# Structural backfill target: Medellín (CO / Antioquia) for existing companies.
# Created inside this migration only when missing — required so NOT NULL geo_city
# can be applied without a separate catalog seed (see no-seed rule: structural
# backfill exception for irreversible schema change).
MEDELLIN_CITY_ID = uuid.UUID('0f15d58f-1ed6-4019-a3b7-22861f9dbc82')
_BOOTSTRAP_COUNTRY_CODE = 'CO'
_BOOTSTRAP_DEPT_CODE = 'ANT'
_BOOTSTRAP_CITY_CODE = 'MED'


def _ensure_bootstrap_city(apps, schema_editor):
    """Ensure the backfill city exists (create CO/ANT/MED if catalog is empty)."""
    Country = apps.get_model('geography_location', 'Country')
    Department = apps.get_model('geography_location', 'Department')
    City = apps.get_model('geography_location', 'City')

    if City.objects.filter(pk=MEDELLIN_CITY_ID).exists():
        return MEDELLIN_CITY_ID

    country, _ = Country.objects.get_or_create(
        code=_BOOTSTRAP_COUNTRY_CODE,
        defaults={'name': 'Colombia', 'is_active': True},
    )
    department, _ = Department.objects.get_or_create(
        country_id=country.id,
        code=_BOOTSTRAP_DEPT_CODE,
        defaults={'name': 'Antioquia', 'is_active': True},
    )
    City.objects.create(
        id=MEDELLIN_CITY_ID,
        department_id=department.id,
        code=_BOOTSTRAP_CITY_CODE,
        name='Medellín',
        is_active=True,
    )
    return MEDELLIN_CITY_ID


def _backfill_geo_city(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    if not Company.objects.filter(geo_city_id__isnull=True).exists():
        return
    city_id = _ensure_bootstrap_city(apps, schema_editor)
    Company.objects.filter(geo_city_id__isnull=True).update(geo_city_id=city_id)


def _clear_geo_city(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    Company.objects.all().update(geo_city_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0005_alter_company_table_alter_domain_table'),
        ('geography_location', '0001_initial_and_geo_country_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='geo_city',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='companies',
                to='geography_location.city',
            ),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['geo_city'], name='idx_companies_geo_city'),
        ),
        migrations.RunPython(_backfill_geo_city, _clear_geo_city),
    ]
