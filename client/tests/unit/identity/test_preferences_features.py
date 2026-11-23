"""Feature-key mapping for PATCH /identity/preferences/ uses the validated body."""

from types import SimpleNamespace
from unittest import TestCase

from client.features.security.identity.identity.presentation.api import (
    UserPreferencesAPIView,
    preference_feature_keys,
)

import pytest

pytestmark = pytest.mark.unit


class TestPreferenceFeatureKeys(TestCase):

    def test_maps_validated_clock_and_date_to_same_feature(self):
        keys = preference_feature_keys({
            'date_format': 'DD/MM/YYYY',
            'time_format': '12',
        })
        self.assertEqual(keys, ['settings.preferences.change-date-format'])

    def test_maps_theme_and_language(self):
        keys = preference_feature_keys({'theme': 'dark', 'language': 'es'})
        self.assertEqual(
            keys,
            [
                'settings.preferences.change-language',
                'settings.preferences.change-theme',
            ],
        )

    def test_ignores_unknown_and_invalid_fields(self):
        self.assertIsNone(preference_feature_keys({'unknown': 'x'}))
        self.assertIsNone(preference_feature_keys({'time_format': '36'}))
        self.assertIsNone(preference_feature_keys({'date_format': 'dd/mm/yyyy'}))

    def test_keeps_valid_fields_when_a_sibling_is_invalid(self):
        keys = preference_feature_keys({
            'theme': 'dark',
            'time_format': '36',
        })
        self.assertEqual(keys, ['settings.preferences.change-theme'])

    def test_non_dict_payload_is_empty(self):
        self.assertIsNone(preference_feature_keys(None))
        self.assertIsNone(preference_feature_keys(['theme']))


class TestUserPreferencesSubscriptionKeys(TestCase):

    def setUp(self):
        self.view = UserPreferencesAPIView()

    def test_get_requires_view_feature(self):
        request = SimpleNamespace(method='GET', data={})
        self.assertEqual(
            self.view.get_subscription_functionality(request),
            'settings.preferences.view',
        )

    def test_patch_uses_validated_body_not_raw_keys(self):
        request = SimpleNamespace(
            method='PATCH',
            data={'time_format': '12', 'bogus': True},
        )
        self.assertEqual(
            self.view.get_subscription_functionality(request),
            ['settings.preferences.change-date-format'],
        )
