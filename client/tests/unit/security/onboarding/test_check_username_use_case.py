"""Unit tests for CheckUsernameAvailabilityUseCase."""
from unittest.mock import MagicMock

import pytest
from django.test import SimpleTestCase

from client.features.security.lifecycle.onboarding.application.use_cases.check_username import (
    CheckUsernameAvailabilityUseCase,
)

pytestmark = pytest.mark.unit


class TestCheckUsernameAvailabilityUseCase(SimpleTestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.use_case = CheckUsernameAvailabilityUseCase(self.repo)

    def test_returns_true_when_username_is_free(self):
        self.repo.username_taken.return_value = False
        self.assertTrue(self.use_case.execute('new_admin'))
        self.repo.username_taken.assert_called_once_with('new_admin')

    def test_returns_false_when_username_is_taken(self):
        self.repo.username_taken.return_value = True
        self.assertFalse(self.use_case.execute('taken_user'))

    def test_strips_whitespace(self):
        self.repo.username_taken.return_value = False
        self.use_case.execute('  MyUser  ')
        self.repo.username_taken.assert_called_once_with('MyUser')

    def test_empty_username_is_not_available(self):
        self.assertFalse(self.use_case.execute('   '))
        self.repo.username_taken.assert_not_called()
