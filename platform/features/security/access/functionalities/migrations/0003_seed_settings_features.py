from django.db import migrations


SETTINGS_FEATURES = [
    {'key': 'settings.company.view',             'label': 'Ver información de la empresa',                'category': 'features'},
    {'key': 'settings.company-config',           'label': 'Configuración general de la empresa',          'category': 'features'},
    {'key': 'settings.warehouse-management',     'label': 'Gestión de bodegas',                           'category': 'features'},
    {'key': 'settings.printers-devices',         'label': 'Configuración de impresoras y dispositivos',   'category': 'features'},
    {'key': 'settings.notifications-config',     'label': 'Configuración de notificaciones',              'category': 'features'},
    {'key': 'settings.document-templates',       'label': 'Gestión de plantillas de documentos',          'category': 'features'},
    {'key': 'settings.currency-config',          'label': 'Configuración de monedas',                     'category': 'features'},
    {'key': 'settings.language-config',          'label': 'Configuración de idioma',                      'category': 'features'},
    {'key': 'settings.timezone-config',          'label': 'Configuración de zona horaria',                'category': 'features'},
    {'key': 'settings.product-categories',       'label': 'Gestión de categorías de productos',           'category': 'features'},
    {'key': 'settings.units-of-measure',         'label': 'Configuración de unidades de medida',          'category': 'features'},
    {'key': 'settings.security-params',          'label': 'Parámetros de seguridad',                      'category': 'features'},
    {'key': 'settings.ui-customization',         'label': 'Personalización de la interfaz',               'category': 'features'},
    {'key': 'settings.subscription-billing',     'label': 'Gestión de suscripción y facturación',         'category': 'features'},
    {'key': 'settings.preferences.view',         'label': 'Acceso al apartado de preferencias',           'category': 'features'},
    {'key': 'settings.subscription.view',        'label': 'Acceso al apartado de suscripcion',            'category': 'features'},
    {'key': 'settings.payment-methods.view',     'label': 'Acceso al apartado de metodos de pago',        'category': 'features'},
    {'key': 'settings.preferences.change-theme', 'label': 'Cambiar apariencia de la aplicacion',          'category': 'features'},
    {'key': 'settings.subscription.upgrade',     'label': 'Cambiar plan de suscripcion',                  'category': 'features'},
    {'key': 'settings.subscription.cancel',      'label': 'Cancelar suscripcion activa',                  'category': 'features'},
    {'key': 'settings.payment-methods.create',   'label': 'Agregar metodo de pago',                       'category': 'features'},
    {'key': 'settings.payment-methods.edit',     'label': 'Editar metodo de pago',                        'category': 'features'},
    {'key': 'settings.payment-methods.toggle',   'label': 'Activar/Inactivar metodo de pago',             'category': 'features'},
    {'key': 'settings.payment-methods.delete',   'label': 'Eliminar metodo de pago',                      'category': 'features'},
    {'key': 'settings.date-format-config',       'label': 'Cambiar formato de fecha de la aplicacion',    'category': 'features'},
]


def seed_settings_features(apps, schema_editor):
    Functionality = apps.get_model('functionalities', 'Functionality')
    Module = apps.get_model('modules', 'Module')

    try:
        module = Module.objects.get(code='settings')
    except Module.DoesNotExist:
        return

    for entry in SETTINGS_FEATURES:
        Functionality.objects.update_or_create(
            key=entry['key'],
            defaults={
                'label':     entry['label'],
                'category':  entry['category'],
                'module':    module,
                'is_active': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('functionalities', '0002_rename_fields'),
        ('modules', '0009_update_orders_route'),
    ]

    operations = [
        migrations.RunPython(seed_settings_features, migrations.RunPython.noop),
    ]
