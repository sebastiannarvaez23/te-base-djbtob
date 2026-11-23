"""
Unit tests for GetAdminUserPreferencesUseCase and UpdateAdminUserPreferencesUseCase.

No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.security.identity.identity.application.use_cases import (
    GetAdminUserPreferencesUseCase,
    UpdateAdminUserPreferencesUseCase,
)
from platform.features.security.identity.identity.domain.schemas import (
    AdminUserPreferencesSchema,
    UpdateAdminUserPreferencesSchema,
)

import pytest

pytestmark = pytest.mark.unit


def _make_preferences_schema(**overrides) -> AdminUserPreferencesSchema:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        language='en',
        theme='light',
        timezone='America/New_York',
        date_format='MM/DD/YYYY',
        time_format='24',
        sidebar_collapsed=False,
        items_per_page=20,
        notifications_enabled=True,
    )
    defaults.update(overrides)
    return AdminUserPreferencesSchema(**defaults)


class TestGetAdminUserPreferencesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetAdminUserPreferencesUseCase(self.mock_repo)
        self.user_id = uuid.uuid4()

    def test_returns_preferences_from_repository(self):
        prefs = _make_preferences_schema(user_id=self.user_id)
        self.mock_repo.get_or_create.return_value = prefs

        result = self.use_case.execute(self.user_id)

        self.assertEqual(result.user_id, prefs.user_id)
        self.assertEqual(result.time_format, '24')
        self.mock_repo.get_or_create.assert_called_once_with(self.user_id)


class TestUpdateAdminUserPreferencesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateAdminUserPreferencesUseCase(self.mock_repo)
        self.user_id = uuid.uuid4()

    def test_updates_time_format_to_twelve(self):
        data = UpdateAdminUserPreferencesSchema(time_format='12')
        updated_prefs = _make_preferences_schema(user_id=self.user_id, time_format='12')
        self.mock_repo.update.return_value = updated_prefs

        result = self.use_case.execute(self.user_id, data)

        self.mock_repo.update.assert_called_once_with(self.user_id, data)
        self.assertEqual(result.time_format, '12')

    def test_coerces_numeric_time_format_on_update_schema(self):
        data = UpdateAdminUserPreferencesSchema(time_format=12)
        self.assertEqual(data.time_format, '12')

    def test_rejects_unknown_time_format(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            UpdateAdminUserPreferencesSchema(time_format='36')

    def test_rejects_unknown_date_format(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            UpdateAdminUserPreferencesSchema(date_format='dd/mm/yyyy')
