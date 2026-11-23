"""BuildSessionUseCase with explicit billing recovery access."""
import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.security.lifecycle.auth.application.use_cases import BuildSessionUseCase
from client.features.security.lifecycle.auth.domain.schemas import PreferencesSchema, SubscriptionInfoSchema
from core.access.billing_recovery import LoginAccessResult


class TestBuildSessionRecovery(TestCase):

    def test_uses_recovery_menu_when_access_is_recovery(self):
        session_repo = MagicMock()
        session_repo.get_company_domain.return_value = 'acme.local'
        session_repo.get_or_create_preferences.return_value = PreferencesSchema(
            language='es', theme='light', timezone='UTC',
            date_format='DD/MM/YYYY', time_format='24', sidebar_collapsed=False,
            items_per_page=25, notifications_enabled=True,
        )
        session_repo.get_active_subscription.return_value = SubscriptionInfoSchema(
            id='plan-1', name='Pro', end_date='01/01/2027',
            status='suspended', billing_interval='monthly',
        )
        session_repo.build_billing_recovery_menu.return_value = ([], ['settings.payment-methods.view'])

        user = MagicMock()
        user.id = uuid.uuid4()
        user.username = 'admin'
        user.first_name = 'Admin'
        user.second_name = ''
        user.rol = MagicMock(name='Administrator')
        user.rol.name = 'Administrator'
        user.company = SimpleNamespace(
            id=uuid.uuid4(), name='ACME', nit='1', address='',
            geo_city=SimpleNamespace(
                name='',
                department=SimpleNamespace(
                    name='',
                    country=SimpleNamespace(name='CO'),
                ),
            ),
        )

        with patch(
            'client.features.security.lifecycle.auth.application.use_cases.resolve_profile_picture_url',
            return_value='',
        ), patch(
            'client.features.security.lifecycle.auth.application.use_cases.user_picture_object_key',
            return_value='',
        ):
            session = BuildSessionUseCase(session_repo).execute(
                user,
                access=LoginAccessResult(mode='billing_recovery', subscription_status='suspended'),
            )

        self.assertEqual(session.access_mode, 'billing_recovery')
        self.assertEqual(session.subscription_status, 'suspended')
        session_repo.build_billing_recovery_menu.assert_called_once_with(user.rol)
        session_repo.build_menu.assert_not_called()
