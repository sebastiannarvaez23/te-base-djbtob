"""Unit tests for analytics DATABASES builder (no live Postgres)."""

from __future__ import annotations

import pytest


class _FakeEnv:
    def __init__(self, values: dict):
        self._values = values

    def str(self, key, default=None):
        if key in self._values:
            return self._values[key]
        if default is not None:
            return default
        raise KeyError(key)

    def int(self, key, default=None):
        if key in self._values:
            return int(self._values[key])
        if default is not None:
            return default
        raise KeyError(key)


@pytest.mark.unit
class TestBuildAnalyticsDatabase:

    def test_defaults_to_oltp_credentials_and_wadw_name(self):
        from base.settings.databases import build_analytics_database

        env = _FakeEnv({
            'DB_USER': 'wa_user',
            'DB_PASSWORD': 'secret',
            'DB_HOST': '127.0.0.1',
            'DB_PORT': '3000',
        })
        cfg = build_analytics_database(env)
        assert cfg['ENGINE'] == 'django.db.backends.postgresql'
        assert cfg['NAME'] == 'wadw'
        assert cfg['USER'] == 'wa_user'
        assert cfg['PASSWORD'] == 'secret'
        assert cfg['HOST'] == '127.0.0.1'
        assert cfg['PORT'] == '3000'
        assert cfg['CONN_MAX_AGE'] == 60

    def test_dw_overrides_take_precedence(self):
        from base.settings.databases import build_analytics_database

        env = _FakeEnv({
            'DB_USER': 'oltp',
            'DB_PASSWORD': 'oltp-secret',
            'DB_HOST': '127.0.0.1',
            'DB_PORT': '3000',
            'DW_NAME': 'wadw_prod',
            'DW_USER': 'dw_ro',
            'DW_PASSWORD': 'dw-secret',
            'DW_HOST': 'dw.internal',
            'DW_PORT': '5432',
            'DW_CONN_MAX_AGE': '30',
        })
        cfg = build_analytics_database(env)
        assert cfg['NAME'] == 'wadw_prod'
        assert cfg['USER'] == 'dw_ro'
        assert cfg['PASSWORD'] == 'dw-secret'
        assert cfg['HOST'] == 'dw.internal'
        assert cfg['PORT'] == '5432'
        assert cfg['CONN_MAX_AGE'] == 30
        assert 'search_path' in cfg['OPTIONS']['options']

    def test_defaults_include_search_path(self):
        from base.settings.databases import build_analytics_database

        env = _FakeEnv({
            'DB_USER': 'wa_user',
            'DB_PASSWORD': 'secret',
            'DB_HOST': '127.0.0.1',
            'DB_PORT': '3000',
        })
        cfg = build_analytics_database(env)
        assert 'ctl' in cfg['OPTIONS']['options']
        assert 'dw' in cfg['OPTIONS']['options']
