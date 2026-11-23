# Feature Registry — fuente de verdad de las funcionalidades del cascarón SaaS.
# Cada entrada define una feature que puede ser asignada a un rol.
# Ejecutar `python manage.py sync_features` después de agregar o modificar entradas.
#
# Estructura:
#   module   — código del módulo (coincide con Module.code en la plataforma)
#   key      — identificador único global (formato: "<module>.<feature>")
#   label    — descripción legible (para el panel de administración)
#   category — "features" | "ai" | "api" (api = Integration Application scopes)
#
# El template no trae el catálogo de un producto. Un dominio nuevo añade aquí
# sus keys y el módulo correspondiente.

FEATURE_REGISTRY = [

    # ── Usuarios & Roles ──────────────────────────────────────────────────────
    {'module': 'users_roles', 'key': 'users_roles.create-users',       'label': 'Crear usuarios',                          'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.edit-users',         'label': 'Editar usuarios',                         'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.deactivate-users',   'label': 'Desactivar usuarios',                     'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.create-roles',       'label': 'Crear roles',                             'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.edit-roles',         'label': 'Editar roles',                            'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.assign-roles',       'label': 'Asignar roles a usuarios',                'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.module-permissions', 'label': 'Gestión de permisos por módulo',          'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.feature-permissions','label': 'Gestión de permisos por funcionalidad',   'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.access-history',     'label': 'Historial de accesos',                    'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.two-factor-auth',    'label': 'Autenticación de dos factores (2FA)',     'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.password-recovery',  'label': 'Recuperación de contraseña',              'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.password-policy',    'label': 'Política de contraseñas',                 'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.active-sessions',    'label': 'Sesiones activas',                        'category': 'features'},
    {'module': 'users_roles', 'key': 'users_roles.change-audit',       'label': 'Auditoría de cambios de usuarios',        'category': 'features'},

    # ── Seguridad — acceso a apartados ──────────────────────────────────────────
    {'module': 'users_roles', 'key': 'security.users.view',                       'label': 'Acceso al apartado de usuarios',                  'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.view',                  'label': 'Acceso al apartado de permisos',                  'category': 'features'},

    # ── Seguridad — acciones de usuarios ────────────────────────────────────────
    {'module': 'users_roles', 'key': 'security.users.create',                     'label': 'Crear nuevo usuario',                             'category': 'features'},
    {'module': 'users_roles', 'key': 'security.users.edit',                        'label': 'Editar usuario existente',                        'category': 'features'},
    {'module': 'users_roles', 'key': 'security.users.toggle-active',               'label': 'Activar/Inactivar usuario',                       'category': 'features'},

    # ── Seguridad — acciones de roles y permisos ────────────────────────────────
    {'module': 'users_roles', 'key': 'security.permissions.create-role',           'label': 'Crear nuevo rol',                                 'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.toggle-role',           'label': 'Activar/Inactivar rol',                           'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.edit-role',             'label': 'Editar rol de empresa',                           'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.save',                  'label': 'Guardar permisos de rol',                         'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.view-features',         'label': 'Ver funcionalidades del modulo',                  'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.toggle-module',         'label': 'Activar/Inactivar acceso a modulo',               'category': 'features'},
    {'module': 'users_roles', 'key': 'security.permissions.toggle-feature',        'label': 'Activar/Inactivar funcionalidad individual',      'category': 'features'},

    # ── Integraciones (conexiones que siguen teniendo endpoint) ───────────────
    {'module': 'integrations', 'key': 'integrations.erp-integration', 'label': 'Gestionar conexiones',              'category': 'features'},
    {'module': 'integrations', 'key': 'integrations.webhooks',        'label': 'Webhooks de entrada y salida',      'category': 'features'},
    {'module': 'integrations', 'key': 'integrations.integration-logs','label': 'Logs de integración',               'category': 'features'},
    {'module': 'integrations', 'key': 'integrations.data-mapping',    'label': 'Configuración de mapeos de datos',  'category': 'features'},
    {'module': 'integrations', 'key': 'integrations.oauth',           'label': 'Autenticación OAuth',               'category': 'features'},

    # ── Auditoría ─────────────────────────────────────────────────────────────
    {'module': 'audit', 'key': 'audit.event-logging',           'label': 'Registro de todos los eventos del sistema',    'category': 'features'},
    {'module': 'audit', 'key': 'audit.advanced-filters',        'label': 'Filtros avanzados de auditoría',               'category': 'features'},
    {'module': 'audit', 'key': 'audit.log-export',              'label': 'Exportación de logs',                          'category': 'features'},
    {'module': 'audit', 'key': 'audit.critical-alerts',         'label': 'Alertas por eventos críticos',                 'category': 'features'},
    {'module': 'audit', 'key': 'audit.entity-change-history',   'label': 'Historial de cambios por entidad',             'category': 'features'},
    {'module': 'audit', 'key': 'audit.user-traceability',       'label': 'Trazabilidad de usuarios',                     'category': 'features'},
    {'module': 'audit', 'key': 'audit.access-audit',            'label': 'Auditoría de accesos',                         'category': 'features'},
    {'module': 'audit', 'key': 'audit.config-change-audit',     'label': 'Auditoría de cambios de configuración',        'category': 'features'},
    {'module': 'audit', 'key': 'audit.configurable-retention',  'label': 'Retención configurable de logs',               'category': 'features'},
    {'module': 'audit', 'key': 'audit.audit-reports',           'label': 'Reportes de auditoría',                        'category': 'features'},

    # ── Configuraciones ───────────────────────────────────────────────────────
    {'module': 'settings', 'key': 'settings.company.view',          'label': 'Ver información de la empresa',                'category': 'features'},
    {'module': 'settings', 'key': 'settings.company-config',        'label': 'Configuración general de la empresa',          'category': 'features'},
    {'module': 'settings', 'key': 'settings.printers-devices',      'label': 'Configuración de impresoras y dispositivos',   'category': 'features'},
    {'module': 'settings', 'key': 'settings.notifications-config',  'label': 'Configuración de notificaciones',              'category': 'features'},
    {'module': 'settings', 'key': 'settings.document-templates',    'label': 'Gestión de plantillas de documentos',          'category': 'features'},
    {'module': 'settings', 'key': 'settings.currency-config',       'label': 'Configuración de monedas',                     'category': 'features'},
    {'module': 'settings', 'key': 'settings.security-params',       'label': 'Parámetros de seguridad',                      'category': 'features'},
    {'module': 'settings', 'key': 'settings.backup-config',         'label': 'Configuración de backup',                      'category': 'features'},
    {'module': 'settings', 'key': 'settings.ui-customization',      'label': 'Personalización de la interfaz',               'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription-billing',  'label': 'Gestión de suscripción y facturación',         'category': 'features'},
    {'module': 'settings', 'key': 'settings.profile.view',                  'label': 'Acceso al apartado de perfil',               'category': 'features'},
    {'module': 'settings', 'key': 'settings.preferences.view',              'label': 'Acceso al apartado de preferencias',         'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription.view',             'label': 'Acceso al apartado de suscripcion',          'category': 'features'},
    {'module': 'settings', 'key': 'settings.payment-methods.view',          'label': 'Acceso al apartado de metodos de pago',      'category': 'features'},
    {'module': 'settings', 'key': 'settings.profile.edit',                  'label': 'Editar informacion del perfil',              'category': 'features'},
    {'module': 'settings', 'key': 'settings.preferences.change-theme',       'label': 'Cambiar apariencia de la aplicacion',         'category': 'features'},
    {'module': 'settings', 'key': 'settings.preferences.change-language',    'label': 'Cambiar idioma de la aplicacion',             'category': 'features'},
    {'module': 'settings', 'key': 'settings.preferences.change-timezone',    'label': 'Cambiar zona horaria de la aplicacion',       'category': 'features'},
    {'module': 'settings', 'key': 'settings.preferences.change-date-format', 'label': 'Cambiar formato de fecha de la aplicacion',   'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription.upgrade',          'label': 'Cambiar plan de suscripcion',                'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription.cancel',           'label': 'Cancelar suscripcion activa',                'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription.apply-voucher',    'label': 'Aplicar bono promocional a la suscripcion',  'category': 'features'},
    {'module': 'settings', 'key': 'settings.subscription.view-voucher-applied', 'label': 'Ver bonos promocionales aplicados',      'category': 'features'},
    {'module': 'settings', 'key': 'settings.payment-methods.create',        'label': 'Agregar metodo de pago',                    'category': 'features'},
    {'module': 'settings', 'key': 'settings.payment-methods.edit',          'label': 'Editar metodo de pago',                     'category': 'features'},
    {'module': 'settings', 'key': 'settings.payment-methods.toggle',        'label': 'Activar/Inactivar metodo de pago',           'category': 'features'},
    {'module': 'settings', 'key': 'settings.payment-methods.delete',        'label': 'Eliminar metodo de pago',                   'category': 'features'},

    # ── Assistant ─────────────────────────────────────────────────────────────
    {'module': 'assistant', 'key': 'assistant.chat', 'label': 'Usar el chat del asistente', 'category': 'ai'},
]
