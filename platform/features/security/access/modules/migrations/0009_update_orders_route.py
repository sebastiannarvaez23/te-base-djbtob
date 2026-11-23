from django.db import migrations


def update_orders_route(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    Module.objects.filter(code='orders').update(route='/warehouse/orders')


def revert_orders_route(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    Module.objects.filter(code='orders').update(route='/warehouse/module-in-construction')


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0008_update_location_icon_warehouse'),
    ]

    operations = [
        migrations.RunPython(update_orders_route, reverse_code=revert_orders_route),
    ]
