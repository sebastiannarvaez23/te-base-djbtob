"""Catálogo de tipos de recurso que se pueden compartir por la campanita.

Fuente de verdad en código. Se materializa en ``notification_resource_types``
con ``python manage.py sync_share_resources``.

El template no trae recursos de producto. Un dominio nuevo añade entradas a
``SHAREABLE_RESOURCES``.
"""

from __future__ import annotations


SHAREABLE_RESOURCES: tuple[dict, ...] = ()


def sync_shareable_resources(model) -> tuple[int, int]:
    """Upsert the catalog. Returns ``(created, updated)``."""
    created = updated = 0
    for entry in SHAREABLE_RESOURCES:
        _, was_created = model.objects.update_or_create(
            code=entry['code'],
            defaults={
                'label': entry['label'],
                'icon': entry['icon'],
                'route_template': entry['route_template'],
                'is_active': True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated
