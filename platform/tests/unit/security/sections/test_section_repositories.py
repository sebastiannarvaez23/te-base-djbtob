"""Unit tests for tenant/client section uniqueness."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.security.access.sections.domain.schemas import CreateSectionSchema, UpdateSectionSchema
from platform.features.security.access.sections.infrastructure.repositories import DjangoSectionRepository


@pytest.mark.unit
class TestSectionCodeUniqueness(TestCase):

    def setUp(self):
        self.repo = DjangoSectionRepository()
        self.section_id = uuid.uuid4()
        self.patcher = patch(
            'platform.features.security.access.sections.infrastructure.repositories.Section'
        )
        self.model = self.patcher.start()
        self.qs = MagicMock()
        self.qs.exists.return_value = False
        self.qs.exclude.return_value = self.qs
        self.model.objects.filter.return_value = self.qs

    def tearDown(self):
        self.patcher.stop()

    def test_create_raises_conflict_when_code_taken(self):
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create(
                CreateSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)
        self.model.objects.create.assert_not_called()

    def test_update_raises_conflict_when_code_taken(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'OPS'
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update(
                self.section_id,
                UpdateSectionSchema(code='PLATFORM', name='Operativo', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)
        current.save.assert_not_called()

    def test_update_allows_keeping_own_code(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'PLATFORM'
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = False

        with patch(
            'platform.features.security.access.sections.infrastructure.repositories.SectionSchema.model_validate',
            return_value=MagicMock(code='PLATFORM'),
        ):
            result = self.repo.update(
                self.section_id,
                UpdateSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        current.save.assert_called_once()
        self.assertIsNotNone(result)

    @patch('platform.features.security.access.sections.infrastructure.repositories.next_order', return_value=1)
    def test_create_maps_integrity_error(self, _next_order):
        self.qs.exists.return_value = False
        self.model.objects.create.side_effect = IntegrityError()

        with self.assertRaises(ConflictException) as ctx:
            self.repo.create(
                CreateSectionSchema(code='PLATFORM', name='Sistema', icon='bx-category'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)

    def test_update_maps_integrity_error(self):
        current = MagicMock()
        current.id = self.section_id
        current.code = 'OPS'
        current.save.side_effect = IntegrityError()
        self.model.objects.get.return_value = current
        self.qs.exists.return_value = False

        with self.assertRaises(ConflictException) as ctx:
            self.repo.update(
                self.section_id,
                UpdateSectionSchema(code='PLATFORM'),
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SECTION_DUPLICATE_CODE)
