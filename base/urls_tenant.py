"""Tenant-schema API routes (django-tenants host → ``base.urls``)."""
from django.urls import include, path

tenant_api_v1_patterns = [
    path('identity/module-filters/', include('client.features.security.identity.module_filters.presentation.urls')),
    path('access/entity-grants/', include('client.features.security.access.entity_grants.presentation.urls')),
    path('identity/', include('client.features.security.identity.identity.presentation.urls')),
    path('company-users/', include('client.features.security.identity.users.presentation.urls')),
    path('assistant/', include('client.features.communication.assistant.chat.presentation.urls')),
    path(
        'assistant/credentials/',
        include('client.features.communication.assistant.credentials.presentation.urls'),
    ),
    path('integrations/', include('client.features.integrations.connections.profile.presentation.urls')),
    path('oauth/', include('client.features.integrations.oauth.client.presentation.urls')),
    path('log-config/', include('client.features.logging.system.config.presentation.urls')),
    path('record-trace/', include('client.features.logging.ops.operations.presentation.urls')),
    path('recent-activity/', include('client.features.logging.ops.operations.presentation.activity_urls')),
    path('incidents/', include('platform.features.support.incidents.incident.presentation.urls')),
    path('support/sessions/', include('platform.features.support.sessions.session.presentation.urls')),
    path(
        'support/settings/',
        include('platform.features.support.sessions.session.presentation.settings_client_urls'),
    ),
    path('testimonials/', include('platform.features.configuration.landing.testimonial.presentation.client_urls')),
]
