from django.db import migrations

SEED = [
    ('PURCHASE_ORDER', 'Purchase order', 'shopping-cart', '/warehouse/purchase-orders/:id'),
    ('PICKING', 'Picking', 'list-checks', '/warehouse/pickings/:id'),
    ('DISPATCH', 'Dispatch', 'truck', '/warehouse/dispatches/:id'),
]


def seed(apps, schema_editor):
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    for code, label, icon, route in SEED:
        ResourceType.objects.get_or_create(
            code=code,
            defaults={'label': label, 'icon': icon, 'route_template': route, 'is_active': True},
        )


def unseed(apps, schema_editor):
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    ResourceType.objects.filter(code__in=[s[0] for s in SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_platform', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
