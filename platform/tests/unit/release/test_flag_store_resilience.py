"""FASE 3 — Resiliencia del adaptador CachedDjangoFlagStore (caché / BD)."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.flags import FlagDefinition, FlagStatus, FlagType, is_enabled
from core.flags.domain.schemas import FlagContext
from platform.features.release.feature_flag.feature_flag.infrastructure.flag_store import (
    CachedDjangoFlagStore,
)


class TestCachedDjangoFlagStoreResilience(TestCase):

    def test_cache_read_failure_falls_back_to_repo_then_legacy_on_repo_fail(self):
        with patch('core.cache.decorators.caches') as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            # Miss en caché (None) y luego el repo falla al cargar.
            mock_cache.get.return_value = None

            repo = MagicMock()
            repo.get_active_definitions.side_effect = RuntimeError('db down')
            store = CachedDjangoFlagStore(repository=repo)

            self.assertIsNone(store.get_flag('any.key'))
            self.assertFalse(
                is_enabled('any.key', FlagContext(company_id='co-1'), store=store),
            )

    def test_cache_hit_avoids_repo(self):
        definition = FlagDefinition(
            key='picking.route_v2',
            flag_type=FlagType.RELEASE,
            status=FlagStatus.ACTIVE,
            enabled=True,
            scopes=[],
        )
        with patch('core.cache.decorators.caches') as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = [definition]

            repo = MagicMock()
            store = CachedDjangoFlagStore(repository=repo)

            flag = store.get_flag('picking.route_v2')
            self.assertIsNotNone(flag)
            self.assertTrue(
                is_enabled(
                    'picking.route_v2',
                    FlagContext(company_id='co-1'),
                    store=store,
                ),
            )
            repo.get_active_definitions.assert_not_called()

    def test_cache_get_raises_then_repo_ok(self):
        """Si la lectura de caché falla, el decorador ejecuta el use case igual."""
        definition = FlagDefinition(
            key='picking.route_v2',
            flag_type=FlagType.RELEASE,
            status=FlagStatus.ACTIVE,
            enabled=True,
            scopes=[],
        )
        with patch('core.cache.decorators.caches') as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.side_effect = RuntimeError('redis down')
            mock_cache.set.side_effect = RuntimeError('redis down')

            repo = MagicMock()
            repo.get_active_definitions.return_value = [definition]
            store = CachedDjangoFlagStore(repository=repo)

            self.assertTrue(
                is_enabled(
                    'picking.route_v2',
                    FlagContext(),
                    store=store,
                ),
            )
            repo.get_active_definitions.assert_called()
