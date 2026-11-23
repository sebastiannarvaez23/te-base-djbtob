"""Unit tests for admin catalog uniqueness (sections / modules)."""
import uuid
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.security.access.roles.domain.catalog_schemas import (
    CreateAdminModuleSchema,
    CreateAdminSectionSchema,
    UpdateAdminModuleSchema,
    UpdateAdminSectionSchema,
)
from platform.features.security.access.roles.infrastructure.catalog_repositories import DjangoAdminCatalogRepository


@pytest.mark.unit
class TestAdminCatalogSectionUniqueness(TestCase):

    def setUp(self):
        self.repo = DjangoAdminCatalogRepository()
        self.section_id = uuid.uuid4()
        self.patcher = patch(
            'platform.features.security.access.roles.infrastructure.catalog_repositories.AdminSection'
        )
        self.model = self.patcher.start()
        self.qs = MagicMock()
        self.qs.exists.return_value = False
        self.qs.exclude.return_value = self.qs
        self.model.objects.filter.return_value = self.qs

    def tearDown(self):
        self.patcher.stop()

    def test_update_section_raises_conflict_when_code_taken(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'OPS'
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update_section(
                self.section_id,
                UpdateAdminSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)
        current.save.assert_not_called()

    def test_update_section_allows_keeping_own_code(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'PLATFORM'
        current.name = 'Sistema'
        current.icon = 'bx-category'
        current.order = 1
        current.is_active = True
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = False

        result = self.repo.update_section(
            self.section_id,
            UpdateAdminSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
        )

        current.save.assert_called_once()
        self.assertIsNotNone(result)

    def test_create_section_raises_conflict_when_code_taken(self):
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create_section(
                CreateAdminSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)
        self.model.objects.create.assert_not_called()

    @patch('platform.features.security.access.roles.infrastructure.catalog_repositories.next_order', return_value=1)
    def test_create_section_maps_integrity_error(self, _next_order):
        self.qs.exists.return_value = False
        self.model.objects.create.side_effect = IntegrityError()

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create_section(
                CreateAdminSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)

    def test_update_section_maps_integrity_error(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'OPS'
        current.save.side_effect = IntegrityError()
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = False

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update_section(
                self.section_id,
                UpdateAdminSectionSchema(code='PLATFORM'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)


@pytest.mark.unit
class TestAdminCatalogModuleUniqueness(TestCase):

    def setUp(self):
        self.repo = DjangoAdminCatalogRepository()
        self.module_id = uuid.uuid4()
        self.section_id = uuid.uuid4()
        self.section_patcher = patch(
            'platform.features.security.access.roles.infrastructure.catalog_repositories.AdminSection'
        )
        self.module_patcher = patch(
            'platform.features.security.access.roles.infrastructure.catalog_repositories.AdminModule'
        )
        self.section_model = self.section_patcher.start()
        self.module_model = self.module_patcher.start()
        self.qs = MagicMock()
        self.qs.exists.return_value = False
        self.qs.exclude.return_value = self.qs
        self.module_model.objects.filter.return_value = self.qs
        self.section_model.objects.filter.return_value.exists.return_value = True

    def tearDown(self):
        self.section_patcher.stop()
        self.module_patcher.stop()

    def test_create_module_raises_conflict_when_code_taken(self):
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create_module(
                CreateAdminModuleSchema(
                    code='FEATURES',
                    name='Features',
                    icon='bx-star',
                    route='/features',
                    section_id=self.section_id,
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)
        self.module_model.objects.create.assert_not_called()

    def test_update_module_name_preserves_code(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        current = MagicMock()
        current.id = self.module_id
        current.code = 'FEATURES'
        current.name = 'Features'
        current.description = ''
        current.icon = 'bx-star'
        current.route = '/features'
        current.section_id = self.section_id
        current.order = 1
        current.is_sidebar = True
        current.is_active = True
        current.created_at = now
        current.updated_at = now
        current.section.code = 'PLATFORM'
        current.section.name = 'Sistema'
        current.section.order = 1
        self.module_model.objects.select_related.return_value.get.return_value = current

        result = self.repo.update_module(
            self.module_id,
            UpdateAdminModuleSchema(name='Features Updated'),
        )

        current.save.assert_called_once()
        self.assertIsNotNone(result)
        self.assertEqual(result.code, 'FEATURES')
        self.assertEqual(current.code, 'FEATURES')

    @patch('platform.features.security.access.roles.infrastructure.catalog_repositories.next_order', return_value=1)
    def test_create_module_maps_integrity_error(self, _next_order):
        self.qs.exists.return_value = False
        self.module_model.objects.create.side_effect = IntegrityError()

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create_module(
                CreateAdminModuleSchema(
                    code='FEATURES',
                    name='Features',
                    icon='bx-star',
                    route='/features',
                    section_id=self.section_id,
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)

    def test_update_module_maps_integrity_error(self):
        current = MagicMock()
        current.id = self.module_id
        current.code = 'FEATURES'
        current.save.side_effect = IntegrityError()
        self.module_model.objects.select_related.return_value.get.return_value = current

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update_module(
                self.module_id,
                UpdateAdminModuleSchema(name='Features'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)
