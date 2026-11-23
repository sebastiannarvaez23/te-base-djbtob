"""Unit tests for feature-flag CRUD use cases (FASE 2)."""

from __future__ import annotations

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import ConflictException, NotFoundException, ValidationAppException
from core.errors.codes import AppErrorCode
from core.flags import FlagDefinition, FlagEvaluator, FlagStatus, FlagType, is_enabled
from core.flags.domain.enums import ScopeType
from core.flags.domain.schemas import FlagContext, FlagScope
from platform.features.release.feature_flag.feature_flag.application.use_cases import (
    CreateFeatureFlagUseCase,
    DeleteFeatureFlagUseCase,
    GetActiveFlagsSnapshotUseCase,
    GetAllFeatureFlagsUseCase,
    GetFeatureFlagByIdUseCase,
    SetFeatureFlagStatusUseCase,
    ToggleFeatureFlagEnabledUseCase,
    UpdateFeatureFlagUseCase,
)
from platform.features.release.feature_flag.feature_flag.domain.schemas import (
    CreateFeatureFlagSchema,
    FeatureFlagSchema,
    ScopeInputSchema,
    UpdateFeatureFlagSchema,
)
from platform.features.release.feature_flag.feature_flag.infrastructure.flag_store import (
    CachedDjangoFlagStore,
)


def _flag(**overrides) -> FeatureFlagSchema:
    defaults = dict(
        id=uuid.uuid4(),
        key='picking.route_v2',
        name='Picking route v2',
        description='',
        flag_type='RELEASE',
        status='DRAFT',
        enabled=False,
        owner='',
        scopes=[],
    )
    defaults.update(overrides)
    return FeatureFlagSchema(**defaults)


def _create(**overrides) -> CreateFeatureFlagSchema:
    defaults = dict(
        key='picking.route_v2',
        name='Picking route v2',
        status='DRAFT',
        enabled=False,
    )
    defaults.update(overrides)
    return CreateFeatureFlagSchema(**defaults)


def _patch_read_cache():
    return patch('core.cache.decorators.caches')


def _patch_invalidate():
    return patch('core.cache.invalidation.caches')


class TestCreateFeatureFlagUseCase(TestCase):

    def test_create_success_invalidates_cache(self):
        with _patch_invalidate() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

            repo = MagicMock()
            repo.get_by_key.return_value = None
            created = _flag(status='ACTIVE', enabled=True)
            repo.create.return_value = created

            result = CreateFeatureFlagUseCase(repo).execute(
                _create(status='ACTIVE', enabled=True),
            )

            self.assertEqual(result.key, 'picking.route_v2')
            repo.create.assert_called_once()
            mock_cache.delete.assert_called_once_with('feature_flags')
            mock_cache.delete_pattern.assert_called_once_with('feature_flags:*')

    def test_create_duplicate_key(self):
        repo = MagicMock()
        repo.get_by_key.return_value = _flag()

        with self.assertRaises(ConflictException) as ctx:
            CreateFeatureFlagUseCase(repo).execute(_create())

        self.assertEqual(ctx.exception.code, AppErrorCode.FLAG_DUPLICATE_KEY)
        repo.create.assert_not_called()


class TestGetFeatureFlagUseCases(TestCase):

    def test_get_all(self):
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = None

            repo = MagicMock()
            repo.get_all.return_value = [_flag()]

            result = GetAllFeatureFlagsUseCase(repo).execute()

            self.assertEqual(len(result), 1)
            repo.get_all.assert_called_once()

    def test_get_by_id_not_found(self):
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = None

            repo = MagicMock()
            repo.get_by_id.return_value = None

            with self.assertRaises(NotFoundException) as ctx:
                GetFeatureFlagByIdUseCase(repo).execute(uuid.uuid4())

            self.assertEqual(ctx.exception.code, AppErrorCode.FLAG_NOT_FOUND)


class TestUpdateFeatureFlagUseCase(TestCase):

    def test_update_success(self):
        with _patch_invalidate() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

            flag_id = uuid.uuid4()
            repo = MagicMock()
            repo.get_by_id.return_value = _flag(id=flag_id)
            repo.get_by_key.return_value = None
            updated = _flag(id=flag_id, enabled=True, status='ACTIVE')
            repo.update.return_value = updated

            result = UpdateFeatureFlagUseCase(repo).execute(
                flag_id,
                UpdateFeatureFlagSchema(enabled=True, status='ACTIVE'),
            )

            self.assertTrue(result.enabled)
            self.assertEqual(result.status, 'ACTIVE')
            mock_cache.delete.assert_called_once_with('feature_flags')
            mock_cache.delete_pattern.assert_called_once_with('feature_flags:*')

    def test_update_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None

        with self.assertRaises(NotFoundException):
            UpdateFeatureFlagUseCase(repo).execute(
                uuid.uuid4(),
                UpdateFeatureFlagSchema(enabled=True),
            )

    def test_update_duplicate_key(self):
        flag_id = uuid.uuid4()
        other_id = uuid.uuid4()
        repo = MagicMock()
        repo.get_by_id.return_value = _flag(id=flag_id)
        repo.get_by_key.return_value = _flag(id=other_id, key='other.key')

        with self.assertRaises(ConflictException):
            UpdateFeatureFlagUseCase(repo).execute(
                flag_id,
                UpdateFeatureFlagSchema(key='other.key'),
            )


class TestDeleteFeatureFlagUseCase(TestCase):

    def test_delete_success(self):
        with _patch_invalidate() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

            repo = MagicMock()
            repo.delete.return_value = True

            self.assertTrue(DeleteFeatureFlagUseCase(repo).execute(uuid.uuid4()))
            mock_cache.delete.assert_called_once_with('feature_flags')
            mock_cache.delete_pattern.assert_called_once_with('feature_flags:*')

    def test_delete_not_found(self):
        repo = MagicMock()
        repo.delete.return_value = False

        with self.assertRaises(NotFoundException):
            DeleteFeatureFlagUseCase(repo).execute(uuid.uuid4())


class TestToggleAndStatusUseCases(TestCase):

    def test_toggle_enabled(self):
        with _patch_invalidate() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

            flag_id = uuid.uuid4()
            repo = MagicMock()
            repo.get_by_id.return_value = _flag(id=flag_id)
            repo.update.return_value = _flag(id=flag_id, enabled=True)

            result = ToggleFeatureFlagEnabledUseCase(repo).execute(flag_id, True)

            self.assertTrue(result.enabled)

    def test_set_status(self):
        with _patch_invalidate() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

            flag_id = uuid.uuid4()
            repo = MagicMock()
            repo.get_by_id.return_value = _flag(id=flag_id)
            repo.update.return_value = _flag(id=flag_id, status='CERTIFIED')

            result = SetFeatureFlagStatusUseCase(repo).execute(flag_id, 'CERTIFIED')

            self.assertEqual(result.status, 'CERTIFIED')

    def test_set_invalid_status(self):
        repo = MagicMock()

        with self.assertRaises(ValidationAppException) as ctx:
            SetFeatureFlagStatusUseCase(repo).execute(uuid.uuid4(), 'NOPE')

        self.assertEqual(ctx.exception.code, AppErrorCode.FLAG_INVALID_PAYLOAD)


class TestActiveSnapshotAndStore(TestCase):

    def test_snapshot_returns_definitions(self):
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = None

            repo = MagicMock()
            definition = FlagDefinition(
                key='picking.route_v2',
                flag_type=FlagType.RELEASE,
                status=FlagStatus.ACTIVE,
                enabled=True,
                scopes=[
                    FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1'),
                ],
            )
            repo.get_active_definitions.return_value = [definition]

            result = GetActiveFlagsSnapshotUseCase(repo).execute()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].key, 'picking.route_v2')

    def test_cached_store_feeds_evaluator(self):
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = None

            repo = MagicMock()
            repo.get_active_definitions.return_value = [
                FlagDefinition(
                    key='picking.route_v2',
                    flag_type=FlagType.RELEASE,
                    status=FlagStatus.ACTIVE,
                    enabled=True,
                    scopes=[
                        FlagScope(
                            scope_type=ScopeType.COUNTRY,
                            scope_value='Colombia',
                        ),
                    ],
                ),
            ]
            store = CachedDjangoFlagStore(repository=repo)
            ctx = FlagContext(country='Colombia', company_id='co-1')

            self.assertTrue(FlagEvaluator(store).is_enabled('picking.route_v2', ctx))
            self.assertTrue(is_enabled('picking.route_v2', ctx, store=store))

    def test_non_active_status_not_in_snapshot_path(self):
        """Solo ACTIVE llega al store; CERTIFIED no enciende la lógica nueva."""
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.return_value = None

            repo = MagicMock()
            repo.get_active_definitions.return_value = []
            store = CachedDjangoFlagStore(repository=repo)
            ctx = FlagContext(company_id='co-1')

            self.assertFalse(is_enabled('picking.route_v2', ctx, store=store))

    def test_store_failure_defaults_to_legacy(self):
        with _patch_read_cache() as mock_caches:
            mock_cache = MagicMock()
            mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
            mock_cache.get.side_effect = RuntimeError('redis down')

            repo = MagicMock()
            repo.get_active_definitions.side_effect = RuntimeError('db down')
            store = CachedDjangoFlagStore(repository=repo)

            self.assertIsNone(store.get_flag('any.key'))
            self.assertEqual(store.list_active_flags(), [])
            self.assertFalse(
                is_enabled('any.key', FlagContext(company_id='co-1'), store=store),
            )


class TestCreateSchemaValidation(TestCase):

    def test_rejects_invalid_key(self):
        with self.assertRaises(Exception):
            CreateFeatureFlagSchema(key='Invalid Key', name='Name here')

    def test_accepts_scopes(self):
        schema = CreateFeatureFlagSchema(
            key='orders.wave_v2',
            name='Wave picking v2',
            scopes=[
                ScopeInputSchema(scope_type='CITY', scope_value='Bogotá'),
            ],
        )
        self.assertEqual(schema.scopes[0].scope_type, 'CITY')

    def test_rejects_invalid_scope_type(self):
        with self.assertRaises(Exception):
            ScopeInputSchema(scope_type='ZONE', scope_value='x')


class TestGetFlagStoreFactory(TestCase):

    def test_django_provider(self):
        from core.flags import get_flag_store
        from platform.features.release.feature_flag.feature_flag.infrastructure.flag_store import (
            CachedDjangoFlagStore as Store,
        )

        store = get_flag_store('django')
        self.assertIsInstance(store, Store)
