from django.db import migrations, models


ALL_MODULES = [
    'dashboard', 'orders', 'reception', 'location', 'inventories',
    'picking', 'packing', 'dispatches', 'shipping', 'third_parties',
    'users_roles', 'tasks', 'integrations', 'automation', 'analytics',
    'audit', 'settings',
]

STANDARD_FEATURES = [
    'dashboard.view-summary', 'dashboard.configurable-widgets', 'dashboard.real-time-metrics',
    'dashboard.alerts-notifications', 'dashboard.quick-access', 'dashboard.kpis',
    'orders.create', 'orders.edit', 'orders.cancel', 'orders.view-status',
    'orders.inventory-validation', 'orders.priorities', 'orders.multi-warehouse', 'orders.traceability',
    'reception.create', 'reception.edit', 'reception.quality-control',
    'reception.blind-count', 'reception.location-assignment', 'reception.lot-series-traceability',
    'location.create', 'location.edit', 'location.zone-management',
    'location.warehouse-map', 'location.inventory-relocation', 'location.multi-warehouse',
    'inventories.real-time-view', 'inventories.adjustments', 'inventories.physical-counts',
    'inventories.lot-expiry-control', 'inventories.warehouse-transfers',
    'inventories.movement-history', 'inventories.kardex',
    'picking.create-tasks', 'picking.assign-tasks', 'picking.batch-picking',
    'picking.wave-picking', 'picking.picking-rules', 'picking.traceability',
    'packing.create-tasks', 'packing.product-verification', 'packing.dimensions-weight',
    'packing.label-generation', 'packing.quality-control',
    'dispatches.create', 'dispatches.edit', 'dispatches.carrier-assignment',
    'dispatches.dispatch-guide', 'dispatches.traceability',
    'shipping.carrier-management', 'shipping.tracking', 'shipping.customer-notifications',
    'shipping.label-generation', 'shipping.multi-carrier',
    'third_parties.client-management', 'third_parties.supplier-management',
    'third_parties.contact-info', 'third_parties.credit-control', 'third_parties.classification',
    'users_roles.create-users', 'users_roles.edit-users', 'users_roles.create-roles',
    'users_roles.module-permissions', 'users_roles.feature-permissions', 'users_roles.access-history',
    'tasks.create', 'tasks.assign', 'tasks.status-tracking', 'tasks.deadlines', 'tasks.recurring-tasks',
    'integrations.erp-integration', 'integrations.ecommerce-integration', 'integrations.webhooks',
    'integrations.rest-api', 'integrations.import-export', 'integrations.integration-logs',
    'automation.create-rules', 'automation.event-triggers', 'automation.cron-triggers',
    'automation.chained-actions', 'automation.execution-history',
    'analytics.custom-dashboards', 'analytics.predefined-reports', 'analytics.export-reports',
    'analytics.operational-kpis', 'analytics.operator-productivity',
    'audit.event-logging', 'audit.advanced-filters', 'audit.log-export',
    'audit.critical-alerts', 'audit.user-traceability', 'audit.audit-reports',
    'settings.company-config', 'settings.warehouse-management', 'settings.notifications-config',
    'settings.document-templates', 'settings.security-params', 'settings.subscription-billing',
]

AI_FEATURES = [
    'dashboard.daily-demand-prediction', 'dashboard.predictive-alerts', 'dashboard.smart-day-summary',
    'orders.priority-prediction', 'orders.delay-prediction', 'orders.optimal-warehouse',
    'reception.auto-location-suggestion', 'reception.anomaly-detection',
    'location.optimal-slotting', 'location.occupancy-prediction',
    'inventories.stockout-prediction', 'inventories.abc-classification', 'inventories.demand-prediction',
    'picking.route-optimization', 'picking.order-grouping', 'picking.auto-assignment',
    'packing.optimal-package-recommendation', 'packing.time-prediction',
    'dispatches.route-optimization', 'dispatches.delivery-time-prediction',
    'shipping.optimal-carrier-selection', 'shipping.cost-optimization',
    'third_parties.credit-risk-classification',
    'tasks.auto-prioritization', 'tasks.smart-assignment',
    'analytics.demand-predictive-analysis', 'analytics.trend-detection', 'analytics.improvement-recommendations',
    'automation.rule-suggestion', 'automation.workflow-optimization',
]

PLAN_DATA = {
    'basic': {
        'description': 'Plan básico gratuito para comenzar a digitalizar tu operación.',
        'logo': 'assets/subs/Shield Standard.png',
        'enabled_modules': ['dashboard', 'inventories', 'settings'],
        'enabled_features': [
            'dashboard.view-summary', 'dashboard.alerts-notifications',
            'inventories.real-time-view', 'inventories.adjustments',
            'settings.company-config',
        ],
    },
    'standard': {
        'description': 'Plan estándar ideal para pequeñas y medianas empresas.',
        'logo': 'assets/subs/Shield Basic.png',
        'enabled_modules': [
            'dashboard', 'orders', 'reception', 'inventories',
            'picking', 'dispatches', 'third_parties', 'settings',
        ],
        'enabled_features': [
            'dashboard.view-summary', 'dashboard.real-time-metrics',
            'dashboard.alerts-notifications', 'dashboard.kpis',
            'orders.create', 'orders.edit', 'orders.view-status', 'orders.inventory-validation',
            'reception.create', 'reception.edit', 'reception.quality-control',
            'inventories.real-time-view', 'inventories.adjustments',
            'inventories.physical-counts', 'inventories.movement-history',
            'picking.create-tasks', 'picking.assign-tasks', 'picking.traceability',
            'dispatches.create', 'dispatches.edit', 'dispatches.carrier-assignment',
            'third_parties.client-management', 'third_parties.supplier-management',
            'third_parties.contact-info',
            'settings.company-config', 'settings.warehouse-management',
            'settings.notifications-config',
        ],
    },
    'pro': {
        'description': 'Plan profesional con acceso completo a todos los módulos operativos.',
        'logo': 'assets/subs/Shield Professional.png',
        'enabled_modules': ALL_MODULES,
        'enabled_features': STANDARD_FEATURES,
    },
    'enterprise': {
        'description': 'Plan empresarial con todas las funcionalidades incluyendo inteligencia artificial y soporte dedicado.',
        'logo': 'assets/subs/Shield Enterprise.png',
        'enabled_modules': ALL_MODULES,
        'enabled_features': STANDARD_FEATURES + AI_FEATURES,
    },
}


def populate_subscription_fields(apps, schema_editor):
    Subscription = apps.get_model('subscription', 'Subscription')
    for code, data in PLAN_DATA.items():
        Subscription.objects.filter(code=code).update(
            description=data['description'],
            logo=data['logo'],
            enabled_modules=data['enabled_modules'],
            enabled_features=data['enabled_features'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0004_alter_companysubscription_table_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='Descripción'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='logo',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Logo'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='enabled_modules',
            field=models.JSONField(default=list, verbose_name='Módulos habilitados'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='enabled_features',
            field=models.JSONField(default=list, verbose_name='Funcionalidades habilitadas'),
        ),
        migrations.RunPython(populate_subscription_fields, migrations.RunPython.noop),
    ]
