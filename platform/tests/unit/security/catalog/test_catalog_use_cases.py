"""Unit tests for admin catalog use cases (not-found mapping)."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from platform.features.security.access.roles.application.catalog_use_cases import (
    CreateAdminCatalogFeatureUseCase,
    CreateAdminCatalogModuleUseCase,
    DeleteAdminCatalogFeatureUseCase,
    DeleteAdminCatalogModuleUseCase,
    DeleteAdminSectionUseCase,
    ToggleAdminCatalogModuleUseCase,
    ToggleAdminSectionUseCase,
    UpdateAdminCatalogFeatureUseCase,
    UpdateAdminCatalogModuleUseCase,
    UpdateAdminSectionUseCase,
)
from platform.features.security.access.roles.domain.catalog_schemas import (
    CreateAdminFeatureSchema,
    CreateAdminModuleSchema,
    UpdateAdminFeatureSchema,
    UpdateAdminModuleSchema,
    UpdateAdminSectionSchema,
)


@pytest.mark.unit
class TestAdminCatalogSectionUseCases(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.section_id = uuid.uuid4()

    def test_update_raises_section_not_found(self):
        self.repo.update_section.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            UpdateAdminSectionUseCase(self.repo).execute(
                self.section_id,
                UpdateAdminSectionSchema(name='Sistema'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_NOT_FOUND)

    def test_toggle_raises_section_not_found(self):
        self.repo.toggle_section.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            ToggleAdminSectionUseCase(self.repo).execute(self.section_id)

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_NOT_FOUND)

    def test_delete_raises_section_not_found(self):
        self.repo.delete_section.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            DeleteAdminSectionUseCase(self.repo).execute(self.section_id)

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_NOT_FOUND)


@pytest.mark.unit
class TestAdminCatalogModuleUseCases(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.module_id = uuid.uuid4()

    def test_create_raises_validation_when_section_missing(self):
        self.repo.create_module.return_value = None

        with self.assertRaises(ValidationAppException) as ctx:
            CreateAdminCatalogModuleUseCase(self.repo).execute(
                CreateAdminModuleSchema(
                    code='FEATURES',
                    name='Features',
                    icon='bx-star',
                    section_id=uuid.uuid4(),
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)

    def test_update_raises_module_not_found(self):
        self.repo.update_module.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            UpdateAdminCatalogModuleUseCase(self.repo).execute(
                self.module_id,
                UpdateAdminModuleSchema(name='Features'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_NOT_FOUND)

    def test_toggle_raises_module_not_found(self):
        self.repo.toggle_module.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            ToggleAdminCatalogModuleUseCase(self.repo).execute(self.module_id)

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_NOT_FOUND)

    def test_delete_raises_module_not_found(self):
        self.repo.delete_module.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            DeleteAdminCatalogModuleUseCase(self.repo).execute(self.module_id)

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_NOT_FOUND)


@pytest.mark.unit
class TestAdminCatalogFeatureUseCases(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.feature_id = uuid.uuid4()

    def test_create_raises_validation_when_module_missing(self):
        self.repo.create_feature.return_value = None

        with self.assertRaises(ValidationAppException) as ctx:
            CreateAdminCatalogFeatureUseCase(self.repo).execute(
                CreateAdminFeatureSchema(
                    module='MISSING',
                    key='admin.x',
                    label='X',
                    category='features',
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)

    def test_update_raises_not_found(self):
        self.repo.update_feature.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            UpdateAdminCatalogFeatureUseCase(self.repo).execute(
                self.feature_id,
                UpdateAdminFeatureSchema(label='X'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_NOT_FOUND)

    def test_delete_raises_not_found(self):
        self.repo.delete_feature.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            DeleteAdminCatalogFeatureUseCase(self.repo).execute(self.feature_id)

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_NOT_FOUND)
