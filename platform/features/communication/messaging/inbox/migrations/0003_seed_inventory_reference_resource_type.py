from django.db import migrations

SEED = [
    (
        'INVENTORY_REFERENCE',
        'Inventory reference',
        'package',
        '/warehouse/inventories?reference=:id',
    ),
]


def seed(apps, schema_editor):
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    for code, label, icon, route in SEED:
        ResourceType.objects.get_or_create(
            code=code,
            defaults={
                'label': label,
                'icon': icon,
                'route_template': route,
                'is_active': True,
            },
        )


def unseed(apps, schema_editor):
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    ResourceType.objects.filter(code__in=[s[0] for s in SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_platform', '0002_seed_resource_types'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
