from django.db import migrations

# Public API / inbox labels must be English (frontend owns i18n).
ENGLISH_LABELS = {
    'PURCHASE_ORDER': 'Purchase order',
    'PICKING': 'Picking',
    'DISPATCH': 'Dispatch',
    'INVENTORY_REFERENCE': 'Inventory reference',
}


def forwards(apps, schema_editor):
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    for code, label in ENGLISH_LABELS.items():
        ResourceType.objects.filter(code=code).update(label=label)


def backwards(apps, schema_editor):
    # Best-effort restore of pre-English seed labels.
    ResourceType = apps.get_model('inbox_platform', 'NotificationResourceType')
    spanish = {
        'PURCHASE_ORDER': 'Orden de Compra',
        'PICKING': 'Picking',
        'DISPATCH': 'Despacho',
        'INVENTORY_REFERENCE': 'Referencia de inventario',
    }
    for code, label in spanish.items():
        ResourceType.objects.filter(code=code).update(label=label)


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_platform', '0003_seed_inventory_reference_resource_type'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
