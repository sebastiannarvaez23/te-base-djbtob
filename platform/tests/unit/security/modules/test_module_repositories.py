"""Unit tests for tenant/client module uniqueness."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.security.access.modules.domain.schemas import CreateModuleSchema, UpdateModuleSchema
from platform.features.security.access.modules.infrastructure.repositories import DjangoModuleRepository


@pytest.mark.unit
class TestModuleCodeUniqueness(TestCase):

    def setUp(self):
        self.repo = DjangoModuleRepository()
        self.module_id = uuid.uuid4()
        self.section_id = uuid.uuid4()
        self.section_patcher = patch(
            'platform.features.security.access.modules.infrastructure.repositories.Section'
        )
        self.module_patcher = patch(
            'platform.features.security.access.modules.infrastructure.repositories.Module'
        )
        self.section_model = self.section_patcher.start()
        self.module_model = self.module_patcher.start()
        self.qs = MagicMock()
        self.qs.exists.return_value = False
        self.qs.exclude.return_value = self.qs
        self.module_model.objects.filter.return_value = self.qs
        self.section_model.objects.get.return_value = MagicMock()

    def tearDown(self):
        self.section_patcher.stop()
        self.module_patcher.stop()

    def test_create_raises_conflict_when_code_taken(self):
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create(
                CreateModuleSchema(
                    code='INVENTORY',
                    name='Inventario',
                    icon='bx-cube',
                    route='/inventory',
                    section_id=self.section_id,
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)
        self.module_model.objects.create.assert_not_called()

    def test_update_name_preserves_code(self):
        current = MagicMock()
        current.id = self.module_id
        current.code = 'INVENTORY'
        self.module_model.objects.select_related.return_value.get.return_value = current

        with patch(
            'platform.features.security.access.modules.infrastructure.repositories.ModuleSchema.model_validate',
            return_value=MagicMock(code='INVENTORY', name='Inventario'),
        ):
            result = self.repo.update(
                self.module_id,
                UpdateModuleSchema(name='Inventario'),
            )

        current.save.assert_called_once()
        self.assertEqual(current.code, 'INVENTORY')
        self.assertIsNotNone(result)

    @patch('platform.features.security.access.modules.infrastructure.repositories.next_order', return_value=1)
    def test_create_maps_integrity_error(self, _next_order):
        self.qs.exists.return_value = False
        self.module_model.objects.create.side_effect = IntegrityError()

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create(
                CreateModuleSchema(
                    code='INVENTORY',
                    name='Inventario',
                    icon='bx-cube',
                    route='/inventory',
                    section_id=self.section_id,
                ),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)

    def test_update_maps_integrity_error(self):
        current = MagicMock()
        current.id = self.module_id
        current.code = 'INVENTORY'
        current.save.side_effect = IntegrityError()
        self.module_model.objects.select_related.return_value.get.return_value = current

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update(
                self.module_id,
                UpdateModuleSchema(name='Inventario'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)
