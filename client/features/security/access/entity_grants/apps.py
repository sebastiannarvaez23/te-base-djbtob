from django.apps import AppConfig


class EntityGrantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.security.access.entity_grants'
    label = 'entity_grants'
    verbose_name = 'Accesos por entidad'

    def ready(self):
        from core.access.entity_scope import register_grant_loader, register_grant_writer
        from client.features.security.access.entity_grants.infrastructure.repositories import (
            grant_entity,
            load_granted_ids,
        )

        register_grant_loader(load_granted_ids)
        register_grant_writer(grant_entity)
