import uuid
from django.db import migrations


ROLES = [
    'Administrator',
    'Operations Manager',
    'Operator',
    'Finance',
]


def seed_roles(apps, schema_editor):
    Rol = apps.get_model('registration', 'Rol')
    for name in ROLES:
        Rol.objects.get_or_create(name=name)


def delete_roles(apps, schema_editor):
    Rol = apps.get_model('registration', 'Rol')
    Rol.objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_code=delete_roles),
    ]
