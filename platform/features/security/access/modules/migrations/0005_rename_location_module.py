from django.db import migrations


def rename_location_module(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    Module.objects.filter(code='location').update(
        name='Almacenes',
        icon='bx-buildings',
        description='Gestión de almacenes, ubicaciones y posiciones de inventario',
    )


def reverse_rename_location_module(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    Module.objects.filter(code='location').update(
        name='Ubicación',
        icon='bx-map-pin',
        description='Gestión de ubicaciones y posiciones',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0004_finalize_section_fk'),
    ]

    operations = [
        migrations.RunPython(
            rename_location_module,
            reverse_code=reverse_rename_location_module,
        ),
    ]
