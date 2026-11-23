"""UpdateUserProfileUseCase: merged invariants and document uniqueness."""
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from client.features.security.identity.identity.application.use_cases import UpdateUserProfileUseCase
from client.features.security.identity.identity.domain.schemas import (
    UpdateUserProfileSchema,
    UserProfileSchema,
)
from core.errors import AppErrorCode, ConflictException, ValidationAppException

pytestmark = pytest.mark.unit


def _profile(**overrides) -> UserProfileSchema:
    defaults = dict(
        id=uuid4(),
        username='owner1',
        first_name='Jane',
        second_name='',
        last_name='Doe',
        second_last_name='Smith',
        document_type='CC',
        document_number='1144205897',
        email='jane@example.com',
        telephone='3001234567',
        phone_country_code='CO',
    )
    defaults.update(overrides)
    return UserProfileSchema(**defaults)


class TestUpdateUserProfileUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.use_case = UpdateUserProfileUseCase(self.repo)
        self.current = _profile()
        self.repo.get.return_value = self.current
        self.repo.document_taken.return_value = False
        self.repo.update.return_value = self.current

    def test_partial_telephone_patch_uses_stored_country(self):
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(
                self.current.id,
                UpdateUserProfileSchema(telephone='5551234'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)
        self.repo.update.assert_not_called()

    def test_partial_name_patch_keeps_valid_stored_identity(self):
        self.use_case.execute(
            self.current.id,
            UpdateUserProfileSchema(first_name='Janet'),
        )
        self.repo.update.assert_called_once()

    def test_duplicate_document_raises_conflict(self):
        self.repo.document_taken.return_value = True
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(
                self.current.id,
                UpdateUserProfileSchema(document_number='9999999999'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.USER_DUPLICATE_DOCUMENT)
        self.repo.update.assert_not_called()

    def test_returns_none_when_profile_missing(self):
        self.repo.get.return_value = None
        result = self.use_case.execute(uuid4(), UpdateUserProfileSchema(first_name='Jane'))
        self.assertIsNone(result)
