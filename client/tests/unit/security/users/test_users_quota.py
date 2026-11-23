"""Unit tests for company user quota gates."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.enforcement import USERS_QUOTA_FEATURE
from core.errors.codes import AppErrorCode
from core.errors.exceptions import SubscriptionException

from client.features.security.identity.users.application.use_cases import (
    CreateCompanyUserUseCase,
    ToggleCompanyUserActiveUseCase,
)
from client.features.security.identity.users.domain.schemas import (
    CompanyUserSchema,
    CreateCompanyUserSchema,
)


from client.features.security.lifecycle.registration.domain.schemas import RolSchema


def _user_schema(**kwargs):
    defaults = {
        'id': uuid.uuid4(),
        'first_name': 'A',
        'last_name': 'B',
        'email': 'a@b.com',
        'username': 'ab',
        'telephone': '1',
        'rol': RolSchema(id=uuid.uuid4(), name='Operator'),
        'is_active': True,
        'picture': None,
    }
    defaults.update(kwargs)
    return CompanyUserSchema(**defaults)


class TestCreateCompanyUserQuota(TestCase):
    def test_raises_when_quota_exceeded(self):
        repo = MagicMock()
        company_id = uuid.uuid4()
        schema = CreateCompanyUserSchema(
            first_name='N',
            last_name='U',
            second_last_name='Perez',
            document_type='CC',
            document_number='1144205897',
            birth_date='1990-05-15',
            email='n@u.com',
            username='nu',
            telephone='1',
            password='secret123',
            rol_id=uuid.uuid4(),
            company_id=company_id,
        )
        with patch(
            'client.features.security.identity.users.application.use_cases._ensure_users_quota',
            side_effect=SubscriptionException(AppErrorCode.SUB_QUOTA_EXCEEDED),
        ):
            uc = CreateCompanyUserUseCase(repo)
            with self.assertRaises(SubscriptionException) as ctx:
                uc.execute(schema)
            self.assertEqual(ctx.exception.code, AppErrorCode.SUB_QUOTA_EXCEEDED)
        repo.create.assert_not_called()

    def test_creates_when_quota_allows(self):
        repo = MagicMock()
        repo.create.return_value = _user_schema()
        company_id = uuid.uuid4()
        schema = CreateCompanyUserSchema(
            first_name='N',
            last_name='U',
            second_last_name='Perez',
            document_type='CC',
            document_number='1144205897',
            birth_date='1990-05-15',
            email='n@u.com',
            username='nu',
            telephone='1',
            password='secret123',
            rol_id=uuid.uuid4(),
            company_id=company_id,
        )
        with patch('client.features.security.identity.users.application.use_cases._ensure_users_quota'):
            uc = CreateCompanyUserUseCase(repo)
            uc.execute(schema)
        repo.create.assert_called_once()


class TestToggleCompanyUserQuota(TestCase):
    def test_activation_blocked_when_quota_full(self):
        repo = MagicMock()
        user_id = uuid.uuid4()
        company_id = uuid.uuid4()
        repo.get_by_id.return_value = _user_schema(id=user_id, is_active=False)
        with patch(
            'client.features.security.identity.users.application.use_cases._ensure_users_quota',
            side_effect=SubscriptionException(AppErrorCode.SUB_QUOTA_EXCEEDED),
        ):
            uc = ToggleCompanyUserActiveUseCase(repo)
            with self.assertRaises(SubscriptionException):
                uc.execute(user_id, company_id)
        repo.toggle_active.assert_not_called()

    def test_deactivation_skips_quota_check(self):
        repo = MagicMock()
        user_id = uuid.uuid4()
        company_id = uuid.uuid4()
        repo.get_by_id.return_value = _user_schema(id=user_id, is_active=True)
        repo.toggle_active.return_value = _user_schema(id=user_id, is_active=False)
        uc = ToggleCompanyUserActiveUseCase(repo)
        uc.execute(user_id, company_id)
        repo.toggle_active.assert_called_once_with(user_id, company_id)
