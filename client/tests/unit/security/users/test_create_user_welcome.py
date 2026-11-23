"""CreateCompanyUserUseCase sends collaborator welcome inbox notification."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.security.lifecycle.registration.domain.schemas import RolSchema
from client.features.security.identity.users.application.use_cases import CreateCompanyUserUseCase
from client.features.security.identity.users.domain.schemas import (
    CompanyUserSchema,
    CreateCompanyUserSchema,
)


def _created_user(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        first_name='Luis',
        last_name='Gómez',
        email='luis@acme.com',
        username='luis@acme.com',
        telephone='300',
        rol=RolSchema(id=uuid.uuid4(), name='Operador'),
        is_active=True,
        picture=None,
    )
    defaults.update(overrides)
    return CompanyUserSchema(**defaults)


class TestCreateCompanyUserWelcomeNotification(TestCase):

    @patch('client.features.security.identity.users.application.use_cases.AccessChecker')
    @patch('client.features.security.identity.users.application.use_cases.Company')
    @patch('client.features.security.lifecycle.registration.models.User')
    @patch(
        'platform.features.communication.notification.dispatchers.dispatch_welcome_user',
    )
    @patch(
        'client.features.communication.messaging.inbox.application.welcome_notifier.notify_collaborator_welcome',
    )
    def test_create_user_triggers_collaborator_welcome(
        self, mock_inbox, mock_email, MockUser, MockCompany, _checker,
    ):
        company_id = uuid.uuid4()
        company = MagicMock()
        company.schema_name = 'acme'
        company.name = 'ACME SAS'
        MockCompany.objects.filter.return_value.only.return_value.first.return_value = company
        MockCompany.objects.filter.return_value.first.return_value = company

        user_orm = MagicMock()
        MockUser.objects.filter.return_value.first.return_value = user_orm

        created = _created_user()
        repo = MagicMock()
        repo.create.return_value = created
        data = CreateCompanyUserSchema(
            first_name='Luis',
            last_name='Gómez',
            second_last_name='Rojas',
            document_type='CC',
            document_number='1144205897',
            birth_date='1990-05-15',
            email='luis@acme.com',
            username='luis@acme.com',
            telephone='300',
            password='Secret123!',
            rol_id=uuid.uuid4(),
            company_id=company_id,
        )

        result = CreateCompanyUserUseCase(repo).execute(data)

        self.assertEqual(result, created)
        mock_inbox.assert_called_once_with(
            schema_name='acme',
            user_id=created.id,
            user_name='Luis Gómez',
            company_name='ACME SAS',
        )
        mock_email.assert_called_once_with(user=user_orm, company=company)
