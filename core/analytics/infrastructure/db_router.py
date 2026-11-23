"""
Database router for the analytics alias (wadw).

Must be registered **before** ``TenantSyncRouter``: that router returns
``False`` for any alias other than the tenant DB (``default``), which would
block analytics migrations forever if it ran first.

App labels in ``ANALYTICS_APP_LABELS`` are reserved for Fase 2+ control /
dimensional apps. Until then the set may be empty — the router still
prevents OLTP apps from migrating onto ``analytics``.
"""

from __future__ import annotations

# Extended when the control-plane Django app is registered (Fase 2).
ANALYTICS_APP_LABELS: frozenset[str] = frozenset({'analytics_ctl'})

ANALYTICS_DB_ALIAS = 'analytics'


class AnalyticsRouter:
    """Route analytics models to ``DATABASES['analytics']``; keep OLTP out."""

    route_app_labels = ANALYTICS_APP_LABELS
    analytics_db = ANALYTICS_DB_ALIAS

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.analytics_db
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.analytics_db
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = self.route_app_labels
        if obj1._meta.app_label in labels or obj2._meta.app_label in labels:
            return obj1._meta.app_label in labels and obj2._meta.app_label in labels
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == self.analytics_db
        if db == self.analytics_db:
            return False
        return None
