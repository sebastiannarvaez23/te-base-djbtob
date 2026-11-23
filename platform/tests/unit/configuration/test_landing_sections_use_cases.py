"""Unit tests for landing section visibility use cases."""
import pytest
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

pytestmark = pytest.mark.unit

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from platform.features.configuration.landing.landing.application.use_cases import (
    GetPublicLandingSectionsUseCase,
    ListLandingSectionsUseCase,
    ToggleLandingSectionUseCase,
)
from platform.features.configuration.landing.landing.domain.catalog import LANDING_SECTION_CATALOG
from platform.features.configuration.landing.landing.domain.schemas import LandingSectionSchema


def _section(key='hero', visible=True, order=1) -> LandingSectionSchema:
    return LandingSectionSchema(
        id=uuid4(),
        key=key,
        is_visible=visible,
        sort_order=order,
        label_es=key,
        label_en=key,
    )


class TestListLandingSectionsUseCase(TestCase):

    def test_fills_missing_catalog_rows_as_visible(self):
        repo = MagicMock()
        repo.list_all.return_value = [_section('pricing', False, 8)]
        rows = ListLandingSectionsUseCase(repo).execute()
        self.assertEqual(len(rows), len(LANDING_SECTION_CATALOG))
        by_key = {r.key: r for r in rows}
        self.assertFalse(by_key['pricing'].is_visible)
        self.assertTrue(by_key['hero'].is_visible)
        self.assertIsNone(by_key['hero'].id)


class TestToggleLandingSectionUseCase(TestCase):

    def test_rejects_unknown_key(self):
        repo = MagicMock()
        with self.assertRaises(ValidationAppException) as ctx:
            ToggleLandingSectionUseCase(repo).execute('nope', False)
        self.assertEqual(ctx.exception.code, AppErrorCode.LANDING_SECTION_UNKNOWN)

    def test_updates_existing(self):
        repo = MagicMock()
        updated = _section('faq', False, 10)
        repo.set_visibility.return_value = updated
        result = ToggleLandingSectionUseCase(repo).execute('faq', False)
        self.assertFalse(result.is_visible)
        repo.set_visibility.assert_called_once_with('faq', False)

    def test_upserts_when_missing(self):
        repo = MagicMock()
        repo.set_visibility.return_value = None
        created = _section('cta', True, 12)
        repo.upsert.return_value = created
        result = ToggleLandingSectionUseCase(repo).execute('cta', True)
        self.assertEqual(result.key, 'cta')
        repo.upsert.assert_called_once()


class TestGetPublicLandingSectionsUseCase(TestCase):

    def test_defaults_missing_to_true(self):
        repo = MagicMock()
        repo.list_all.return_value = [_section('ai', False, 4)]
        result = GetPublicLandingSectionsUseCase(repo).execute()
        self.assertFalse(result.sections['ai'])
        self.assertTrue(result.sections['hero'])
        self.assertEqual(len(result.sections), len(LANDING_SECTION_CATALOG))
