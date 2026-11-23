import uuid
from django.db import migrations

SECTIONS = [
    # code, name, order
    ('none',        'General',             0),
    ('operational', 'Operativo',           1),
    ('management',  'Gestión',             2),
    ('analytics',   'Analítica y Control', 3),
    ('system',      'Sistema',             4),
]


def seed_sections(apps, schema_editor):
    Section = apps.get_model('sections', 'Section')
    for code, name, order in SECTIONS:
        Section.objects.get_or_create(
            code=code,
            defaults=dict(id=uuid.uuid4(), name=name, order=order, is_active=True),
        )


def unseed_sections(apps, schema_editor):
    Section = apps.get_model('sections', 'Section')
    Section.objects.filter(code__in=[row[0] for row in SECTIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sections', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_sections, reverse_code=unseed_sections),
    ]
