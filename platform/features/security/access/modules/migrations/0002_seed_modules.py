import uuid
from django.db import migrations


MODULES = [
    # code, name, description, icon, route, section, order
    ('dashboard',     'Inicio',            'Panel principal del sistema',               'bx-grid-alt',       '/warehouse/module-in-construction', 'none',        1),
    ('orders',        'Pedidos',           'Gestión de órdenes de entrada',             'bx-receipt',        '/warehouse/orders',                'operational', 1),
    ('reception',     'Recepción',         'Recepción de mercancía en bodega',          'bx-door-open',      '/warehouse/module-in-construction', 'operational', 2),
    ('location',      'Ubicación',         'Gestión de ubicaciones y posiciones',       'bx-map-pin',        '/warehouse/module-in-construction', 'operational', 3),
    ('inventories',   'Inventarios',       'Control y consulta de inventarios',         'bx-coin-stack',     '/warehouse/module-in-construction', 'operational', 4),
    ('picking',       'Picking',           'Alistamiento y despacho de pedidos',        'bx-basket',         '/warehouse/picking',               'operational', 5),
    ('packing',       'Empaque',           'Empaque y consolidación de cajas',          'bx-package',        '/warehouse/module-in-construction', 'operational', 6),
    ('dispatches',    'Despachos',         'Gestión de órdenes de despacho',            'bxs-truck',         '/warehouse/module-in-construction', 'operational', 7),
    ('shipping',      'Envíos',            'Gestión de envíos y transportistas',        'bxs-plane-alt',     '/warehouse/module-in-construction', 'operational', 8),
    ('third_parties', 'Terceros',          'Administración de clientes y proveedores',  'bx-group',          '/warehouse/module-in-construction', 'management',  1),
    ('users_roles',   'Usuarios y Roles',  'Gestión de usuarios y roles de acceso',     'bx-user-check',     '/security/users-roles',            'management',  2),
    ('tasks',         'Tareas',            'Seguimiento de tareas y actividades',       'bx-task',           '/warehouse/module-in-construction', 'management',  3),
    ('integrations',  'Integraciones',     'Conexiones con sistemas externos',          'bx-link-external',  '/warehouse/module-in-construction', 'management',  4),
    ('automation',    'Automatización',    'Flujos automatizados y bots de proceso',    'bxs-bot',           '/warehouse/automation',            'management',  5),
    ('analytics',     'Analítica',         'Dashboards e indicadores de desempeño',     'bx-pie-chart-alt-2','/warehouse/module-in-construction', 'analytics',   1),
    ('audit',         'Auditoría',         'Historial de cambios y trazabilidad',       'bx-history',        '/warehouse/module-in-construction', 'analytics',   2),
    ('settings',      'Configuración',     'Preferencias y configuración del sistema',  'bx-cog',            '/security/settings',               'system',      1),
]


def seed_modules(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    for code, name, description, icon, route, section, order in MODULES:
        Module.objects.get_or_create(
            code=code,
            defaults=dict(
                id=uuid.uuid4(),
                name=name,
                description=description,
                icon=icon,
                route=route,
                section=section,
                order=order,
                is_active=True,
            ),
        )


def unseed_modules(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    codes = [row[0] for row in MODULES]
    Module.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_modules, reverse_code=unseed_modules),
    ]
