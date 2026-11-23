from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from platform.features.billing.subscription.subscription.presentation.api import (
    UpgradeView, CancelView, ReactivateView, SubscriptionChangeStatusView,
    RetryPaymentView,
)
from platform.features.billing.subscription.subscription.presentation.public_api import (
    PublicSubscriptionCatalogAPIView,
)
from platform.features.configuration.landing.landing.presentation.public_api import (
    PublicLandingSectionsAPIView,
)
from platform.features.configuration.landing.testimonial.presentation.public_api import (
    PublicTestimonialsAPIView,
)
from base.urls_tenant import tenant_api_v1_patterns

schema_view = get_schema_view(
   openapi.Info(
      title="Documentacion de API",
      default_version='v1',
      description="Documentacion publica de API de WMS",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="narvaezsebas8@gmail.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.IsAuthenticated,),
)

# ── API v1 routes ─────────────────────────────────────────────────────────────

api_v1_patterns = [
    *tenant_api_v1_patterns,

    # Security - client (shared schema)
    path('auth/', include('client.features.security.lifecycle.auth.presentation.urls')),
    path('company-roles/', include('client.features.security.access.roles.presentation.urls')),
    path('company-features/', include('client.features.security.access.features.presentation.urls')),
    path('onboarding/', include('client.features.security.lifecycle.onboarding.presentation.urls')),

    # Security - platform
    path('platform/auth/', include('platform.features.security.auth.auth.presentation.urls')),
    path('platform/roles/', include('platform.features.security.access.roles.presentation.urls')),
    path('platform/admin-catalog/', include('platform.features.security.access.roles.presentation.catalog_urls')),
    path('platform/users/', include('platform.features.security.identity.users.presentation.urls')),
    path('platform/identity/', include('platform.features.security.identity.identity.presentation.urls')),
    path('platform/sections/', include('platform.features.security.access.sections.presentation.urls')),
    path('platform/functionalities/', include('platform.features.security.access.functionalities.presentation.urls')),
    path('platform/modules/', include('platform.features.security.access.modules.presentation.urls')),
    path('companies/', include('platform.features.company.tenant.company.presentation.urls')),

    # Public catalog (anonymous; consumed by the onboarding wizard and
    # marketing pages). Distinct from /billing/subscriptions/ which is
    # the admin CRUD.
    path('subscriptions/', PublicSubscriptionCatalogAPIView.as_view(), name='public-subscriptions'),
    path('landing/sections/', PublicLandingSectionsAPIView.as_view(), name='public-landing-sections'),
    path('landing/testimonials/', PublicTestimonialsAPIView.as_view(), name='public-landing-testimonials'),
    path('locations/', include('platform.features.geography.location.location.presentation.public_urls')),

    # Billing
    path('billing/subscriptions/', include('platform.features.billing.subscription.subscription.presentation.urls')),
    path('billing/subscriptions/upgrade/', UpgradeView.as_view()),
    path('billing/subscriptions/cancel/', CancelView.as_view()),
    path('billing/subscriptions/reactivate/', ReactivateView.as_view()),
    path('billing/subscriptions/retry-payment/', RetryPaymentView.as_view()),
    path('billing/subscriptions/change-status/', SubscriptionChangeStatusView.as_view()),
    path('billing/subscription-modules/', include('platform.features.billing.subscription.subscription_module.presentation.urls')),
    path('billing/subscription-functionalities/', include('platform.features.billing.subscription.subscription_functionality.presentation.urls')),
    path('billing/complements/', include('platform.features.billing.complement.entitlement.presentation.urls')),
    path('billing/subscription-limits/', include('platform.features.billing.subscription.subscription_limit.presentation.urls')),
    path('billing/payment-methods/', include('platform.features.billing.commerce.payment_method.presentation.urls')),
    path('billing/invoices/', include('platform.features.billing.commerce.invoice.presentation.urls')),
    path('billing/charges/', include('platform.features.billing.commerce.payments.presentation.urls')),
    path('billing/refunds/', include('platform.features.billing.commerce.refund.presentation.urls')),
    path('billing/webhooks/', include('platform.features.billing.commerce.payments.presentation.webhook_urls')),
    path('ecosystem/webhooks/', include('platform.features.billing.commerce.invoice.presentation.neurana_webhook_urls')),
    path('platform/promotions/', include('platform.features.billing.commerce.promotion.presentation.urls_admin')),
    path('promotions/', include('platform.features.billing.commerce.promotion.presentation.urls_tenant')),

    # Communication
    path('platform/email-senders/', include('platform.features.communication.email.email_sender.presentation.urls')),
    path('platform/email-templates/', include('platform.features.communication.email.email_template.presentation.urls')),
    path('platform/policies/', include('platform.features.compliance.policy.policy.presentation.urls')),
    path('platform/locations/', include('platform.features.geography.location.location.presentation.urls')),
    path('platform/currencies/', include('platform.features.geography.currency.currency.presentation.urls')),
    path('platform/countries/', include('platform.features.geography.currency.currency.presentation.country_urls')),
    path('policies/', include('platform.features.compliance.policy.policy.presentation.client_urls')),

    # Notifications — campanita (usuario de empresa) + admin outbox
    path('client/inbox/', include('client.features.communication.messaging.inbox.presentation.urls')),
    path('platform/inbox/', include('platform.features.communication.messaging.inbox.presentation.urls')),

    # Documents
    path('platform/document-templates/', include('platform.features.documents.document_template.document_template.presentation.urls')),

    # Sessions
    path('platform/sessions/', include('platform.features.security.identity.sessions.presentation.urls')),

    # Configuration
    path('platform/parameter-types/', include('platform.features.configuration.parameters.parameter_type.presentation.urls')),
    path('platform/parameters/', include('platform.features.configuration.parameters.parameter.presentation.urls')),
    path(
        'platform/admin-parameter-types/',
        include(
            'platform.features.configuration.admin_parameters.admin_parameter_type.presentation.urls',
        ),
    ),
    path(
        'platform/admin-parameters/',
        include(
            'platform.features.configuration.admin_parameters.admin_parameter.presentation.urls',
        ),
    ),
    path('platform/landing-sections/', include('platform.features.configuration.landing.landing.presentation.urls')),
    path('platform/testimonials/', include('platform.features.configuration.landing.testimonial.presentation.urls')),
    path('platform/assistant-settings/', include('platform.features.configuration.assistant.assistant.presentation.urls')),
    path('platform/ai/model-routing/', include('platform.features.configuration.ai.model_routing.presentation.urls')),
    path('platform/ai/capabilities/', include('platform.features.configuration.ai.capability_control.presentation.urls')),
    path('platform/ai/runs/', include('platform.features.configuration.ai.run_observability.presentation.urls')),
    path('platform/ai/evals/', include('platform.features.configuration.ai.evals.presentation.urls')),
    path('platform/feature-flags/', include('platform.features.release.feature_flag.feature_flag.presentation.urls')),
    path('platform/integrations/catalog/', include('platform.features.integrations.connector_catalog.connector_catalog.presentation.urls')),
    path('platform/integrations/health/', include('platform.features.integrations.connector_catalog.connector_catalog.presentation.health_urls')),

    # Support — administración de incidencias (portal admin)
    path('platform/incidents/', include('platform.features.support.incidents.incident.presentation.admin_urls')),
    # Support — monitor de tareas automatizadas
    path('platform/task-monitor/', include('platform.features.support.ops.task_monitor.presentation.admin_urls')),
    path('platform/live-logs/', include('platform.features.support.ops.live_logs.presentation.admin_urls')),
    path('platform/support/sessions/', include('platform.features.support.sessions.session.presentation.admin_urls')),
    path(
        'platform/support/settings/',
        include('platform.features.support.sessions.session.presentation.settings_urls'),
    ),

    path('docs/', include('handbook.features.docs.content.catalog.presentation.urls')),
]

urlpatterns = [
    # Documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redocs/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/', include(api_v1_patterns)),
]

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': settings.STATIC_ROOT,
    }),
]
