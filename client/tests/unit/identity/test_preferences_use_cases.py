"""
Unit tests for GetUserPreferencesUseCase and UpdateUserPreferencesUseCase.

No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from client.features.security.identity.identity.application.use_cases import (
    GetUserPreferencesUseCase,
    UpdateUserPreferencesUseCase,
)
from client.features.security.identity.identity.domain.schemas import (
    UserPreferencesSchema,
    UpdateUserPreferencesSchema,
)


def _make_preferences_schema(**overrides) -> UserPreferencesSchema:
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
    return UserPreferencesSchema(**defaults)


class TestGetUserPreferencesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetUserPreferencesUseCase(self.mock_repo)
        self.user_id = uuid.uuid4()

    def test_returns_preferences_from_repository(self):
        prefs = _make_preferences_schema(user_id=self.user_id)
        self.mock_repo.get_or_create.return_value = prefs

        result = self.use_case.execute(self.user_id)

        self.assertEqual(result.user_id, prefs.user_id)
        self.assertEqual(result.language, 'en')

    def test_calls_get_or_create_with_correct_user_id(self):
        self.mock_repo.get_or_create.return_value = _make_preferences_schema()

        self.use_case.execute(self.user_id)

        self.mock_repo.get_or_create.assert_called_once_with(self.user_id)

    def test_creates_preferences_if_they_do_not_exist(self):
        """get_or_create must create preferences if the user does not have any."""
        new_prefs = _make_preferences_schema(user_id=self.user_id)
        self.mock_repo.get_or_create.return_value = new_prefs

        result = self.use_case.execute(self.user_id)

        self.assertIsNotNone(result)
        self.mock_repo.get_or_create.assert_called_once()


class TestUpdateUserPreferencesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateUserPreferencesUseCase(self.mock_repo)
        self.user_id = uuid.uuid4()

    def test_returns_updated_preferences(self):
        data = UpdateUserPreferencesSchema(language='es', theme='dark')
        updated_prefs = _make_preferences_schema(
            user_id=self.user_id, language='es', theme='dark'
        )
        self.mock_repo.update.return_value = updated_prefs

        result = self.use_case.execute(self.user_id, data)

        self.assertEqual(result.language, 'es')
        self.assertEqual(result.theme, 'dark')

    def test_calls_update_with_correct_user_id_and_data(self):
        data = UpdateUserPreferencesSchema(language='es')
        self.mock_repo.update.return_value = _make_preferences_schema()

        self.use_case.execute(self.user_id, data)

        self.mock_repo.update.assert_called_once_with(self.user_id, data)

    def test_partial_update_does_not_affect_other_fields(self):
        """Only the sent field is updated; the rest is handled by the repository."""
        data = UpdateUserPreferencesSchema(items_per_page=50)
        result_prefs = _make_preferences_schema(
            user_id=self.user_id,
            items_per_page=50,
            language='en',    # unchanged
            theme='light',    # unchanged
        )
        self.mock_repo.update.return_value = result_prefs

        result = self.use_case.execute(self.user_id, data)

        self.assertEqual(result.items_per_page, 50)
        self.assertEqual(result.language, 'en')
        self.assertEqual(result.theme, 'light')

    def test_updates_time_format_to_twelve(self):
        data = UpdateUserPreferencesSchema(time_format='12')
        updated_prefs = _make_preferences_schema(user_id=self.user_id, time_format='12')
        self.mock_repo.update.return_value = updated_prefs

        result = self.use_case.execute(self.user_id, data)

        self.mock_repo.update.assert_called_once_with(self.user_id, data)
        self.assertEqual(result.time_format, '12')
        self.assertEqual(data.time_format, '12')

    def test_coerces_numeric_time_format_on_update_schema(self):
        data = UpdateUserPreferencesSchema(time_format=12)
        self.assertEqual(data.time_format, '12')

    def test_rejects_unknown_time_format(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            UpdateUserPreferencesSchema(time_format='36')

    def test_updates_date_format(self):
        data = UpdateUserPreferencesSchema(date_format='YYYY-MM-DD')
        updated_prefs = _make_preferences_schema(
            user_id=self.user_id, date_format='YYYY-MM-DD',
        )
        self.mock_repo.update.return_value = updated_prefs

        result = self.use_case.execute(self.user_id, data)

        self.mock_repo.update.assert_called_once_with(self.user_id, data)
        self.assertEqual(result.date_format, 'YYYY-MM-DD')

    def test_rejects_unknown_date_format(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            UpdateUserPreferencesSchema(date_format='dd/mm/yyyy')
