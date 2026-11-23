"""Fase 0 — analytics DB alias + router (no Postgres required)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.conf import settings

from core.analytics.infrastructure.db_router import (
    ANALYTICS_DB_ALIAS,
    AnalyticsRouter,
)


def _fake_model(app_label: str):
    return SimpleNamespace(_meta=SimpleNamespace(app_label=app_label))


@pytest.mark.unit
class TestAnalyticsDatabaseSettings:

    def test_analytics_alias_configured(self):
        assert ANALYTICS_DB_ALIAS in settings.DATABASES

    def test_analytics_uses_standard_postgres_engine(self):
        engine = settings.DATABASES[ANALYTICS_DB_ALIAS]['ENGINE']
        assert engine == 'django.db.backends.postgresql'
        assert 'django_tenants' not in engine

    def test_default_still_uses_tenants_backend(self):
        assert 'django_tenants' in settings.DATABASES['default']['ENGINE']

    def test_analytics_router_registered_before_tenant_sync(self):
        routers = list(settings.DATABASE_ROUTERS)
        analytics = 'core.analytics.infrastructure.db_router.AnalyticsRouter'
        tenant = 'django_tenants.routers.TenantSyncRouter'
        assert analytics in routers
        assert tenant in routers
        assert routers.index(analytics) < routers.index(tenant)


@pytest.mark.unit
class TestAnalyticsRouter:

    def setup_method(self):
        self.router = AnalyticsRouter()

    def test_allow_migrate_analytics_ctl_only_on_analytics(self):
        assert self.router.allow_migrate(ANALYTICS_DB_ALIAS, 'analytics_ctl') is True
        assert self.router.allow_migrate('default', 'analytics_ctl') is False

    def test_allow_migrate_blocks_oltp_apps_on_analytics(self):
        assert self.router.allow_migrate(ANALYTICS_DB_ALIAS, 'company') is False

    def test_allow_migrate_defers_default_to_tenant_router(self):
        assert self.router.allow_migrate('default', 'company') is None

    def test_db_for_read_write_unrelated_app_returns_none(self):
        model = _fake_model('company')
        assert self.router.db_for_read(model) is None
        assert self.router.db_for_write(model) is None

    def test_db_for_read_write_analytics_label(self, monkeypatch):
        monkeypatch.setattr(
            self.router,
            'route_app_labels',
            frozenset({'analytics_ctl'}),
        )
        model = _fake_model('analytics_ctl')
        assert self.router.db_for_read(model) == ANALYTICS_DB_ALIAS
        assert self.router.db_for_write(model) == ANALYTICS_DB_ALIAS
        assert self.router.allow_migrate(ANALYTICS_DB_ALIAS, 'analytics_ctl') is True
        assert self.router.allow_migrate('default', 'analytics_ctl') is False

    def test_allow_relation_mixed_oltp_analytics_denied(self, monkeypatch):
        monkeypatch.setattr(
            self.router,
            'route_app_labels',
            frozenset({'analytics_ctl'}),
        )
        analytics = _fake_model('analytics_ctl')
        oltp = _fake_model('company')
        assert self.router.allow_relation(analytics, oltp) is False
        assert self.router.allow_relation(oltp, oltp) is None
