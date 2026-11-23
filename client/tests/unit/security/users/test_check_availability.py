"""Unit tests for company user availability probes."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.security.identity.users.application.check_availability import (
    CheckEmailAvailabilityUseCase,
    CheckUsernameAvailabilityUseCase,
)

USER_PATH = 'client.features.security.identity.users.application.check_availability.User'


class TestCheckUsernameAvailabilityUseCase(TestCase):

    @patch(USER_PATH)
    def test_returns_true_when_username_free(self, MockUser):
        MockUser.objects.filter.return_value.exists.return_value = False
        self.assertTrue(CheckUsernameAvailabilityUseCase().execute('newuser'))

    @patch(USER_PATH)
    def test_returns_false_when_username_taken(self, MockUser):
        MockUser.objects.filter.return_value.exists.return_value = True
        self.assertFalse(CheckUsernameAvailabilityUseCase().execute('taken'))

    def test_returns_false_for_blank_username(self):
        self.assertFalse(CheckUsernameAvailabilityUseCase().execute('   '))


class TestCheckEmailAvailabilityUseCase(TestCase):

    @patch(USER_PATH)
    def test_returns_true_when_email_free(self, MockUser):
        MockUser.objects.filter.return_value.exists.return_value = False
        self.assertTrue(CheckEmailAvailabilityUseCase().execute('new@acme.com'))

    @patch(USER_PATH)
    def test_returns_false_when_email_taken(self, MockUser):
        MockUser.objects.filter.return_value.exists.return_value = True
        self.assertFalse(CheckEmailAvailabilityUseCase().execute('taken@acme.com'))

    def test_returns_false_for_blank_email(self):
        self.assertFalse(CheckEmailAvailabilityUseCase().execute('   '))
