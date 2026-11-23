"""
Unit tests para BuildSessionUseCase.

Verifica que la sesión se construya correctamente a partir de un usuario
autenticado, usando un ISessionRepository mockeado.

No se requiere base de datos.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.security.lifecycle.auth.application.use_cases import BuildSessionUseCase
from client.features.security.lifecycle.auth.domain.schemas import (
    CompanyInfoSchema,
    MenuItemSchema,
    PreferencesSchema,
    SessionSchema,
    SubscriptionInfoSchema,
    UserInfoSchema,
)
from core.access.billing_recovery import LoginAccessResult

_FULL_ACCESS = LoginAccessResult(mode='full')


# ── Helpers ────────────────────────────────────────────────────────────────────

def _preferences(**overrides) -> PreferencesSchema:
    defaults = dict(
        language='es',
        theme='light',
        timezone='America/Bogota',
        date_format='DD/MM/YYYY',
        time_format='24',
        sidebar_collapsed=False,
        items_per_page=20,
        notifications_enabled=True,
    )
    defaults.update(overrides)
    return PreferencesSchema(**defaults)


def _subscription(**overrides) -> SubscriptionInfoSchema:
    defaults = dict(
        id=str(uuid.uuid4()),
        name='Pro',
        end_date='2026-12-31',
        status='active',
    )
    defaults.update(overrides)
    return SubscriptionInfoSchema(**defaults)


def _menu_item(**overrides) -> MenuItemSchema:
    defaults = dict(
        id=str(uuid.uuid4()),
        code='orders',
        name='Pedidos',
        icon='bx-receipt',
        route='/warehouse/orders',
        section='warehouse',
    )
    defaults.update(overrides)
    return MenuItemSchema(**defaults)


def _make_user(company_id=None, rol_name='Operador', has_rol=True):
    """Construye un MagicMock que simula un ORM User."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = 'jsmith'
    user.first_name = 'John'
    user.second_name = ''

    company = MagicMock()
    company.id = company_id or uuid.uuid4()
    company.name = 'Bodega Central'
    company.nit = '900123456-7'
    company.address = 'Calle 10 # 20-30'
    company.geo_city = MagicMock()
    company.geo_city.name = 'Bogotá'
    company.geo_city.department.name = 'Cundinamarca'
    company.geo_city.department.country.name = 'Colombia'
    user.company = company

    if has_rol:
        rol = MagicMock()
        rol.name = rol_name
        user.rol = rol
    else:
        user.rol = None

    return user




# ── BuildSessionUseCase ────────────────────────────────────────────────────────

class TestBuildSessionUseCase(TestCase):

    def setUp(self):
        self.mock_session_repo = MagicMock()
        self.use_case = BuildSessionUseCase(self.mock_session_repo)

        # Defaults que el repo mockeado devuelve en cada llamada
        self.mock_session_repo.get_company_domain.return_value = 'bodega.waapp.co'
        self.mock_session_repo.get_or_create_preferences.return_value = _preferences()
        self.mock_session_repo.get_active_subscription.return_value = _subscription()
        self.mock_session_repo.build_menu.return_value = (
            [_menu_item()],
            ['warehouse.orders.view'],
        )

        pending_patch = patch(
            'client.features.security.lifecycle.auth.application.use_cases.pending_policies_for_user',
            return_value=([], 'CO'),
        )
        idle_patch = patch(
            'client.features.security.lifecycle.auth.application.use_cases.inactivity_minutes',
            return_value=15,
        )
        self.pending_mock = pending_patch.start()
        self.addCleanup(pending_patch.stop)
        self.idle_mock = idle_patch.start()
        self.addCleanup(idle_patch.stop)

    # ------------------------------------------------------------------
    # Estructura de la respuesta
    # ------------------------------------------------------------------

    def test_returns_session_schema_instance(self):
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsInstance(result, SessionSchema)
        self.assertEqual(result.inactivity_minutes, 15)

    def test_session_user_contains_username(self):
        user = _make_user()
        user.username = 'maria.lopez'

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.user.username, 'maria.lopez')

    def test_session_user_contains_given_names(self):
        user = _make_user()
        user.first_name = 'María'
        user.second_name = 'José'

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.user.first_name, 'María')
        self.assertEqual(result.user.second_name, 'José')

    def test_session_user_second_name_empty_when_missing(self):
        user = _make_user()
        user.first_name = 'Ana'
        user.second_name = None

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.user.first_name, 'Ana')
        self.assertEqual(result.user.second_name, '')

    def test_session_user_contains_rol_name(self):
        user = _make_user(rol_name='Supervisor')

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.user.rol, 'Supervisor')

    def test_session_user_rol_is_none_when_user_has_no_rol(self):
        user = _make_user(has_rol=False)

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsNone(result.user.rol)

    def test_session_user_id_is_string(self):
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsInstance(result.user.id, str)

    def test_session_user_picture_uses_default_when_no_custom_picture(self):
        user = _make_user()
        user.picture = None

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIn('client/assets/profile/avatar.png', result.user.picture)

    def test_session_user_picture_uses_custom_picture_key(self):
        user = _make_user()
        user.picture = MagicMock()
        user.picture.name = 'client/tenants/acme/assets/profiles/pic-jsmith.jpg'

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIn('pic-jsmith.jpg', result.user.picture)
        self.assertNotIn('avatar.png', result.user.picture)

    # ------------------------------------------------------------------
    # Información de la empresa
    # ------------------------------------------------------------------

    def test_session_company_contains_name(self):
        user = _make_user()
        user.company.name = 'Empresa XYZ'

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.company.name, 'Empresa XYZ')

    def test_session_company_contains_domain_from_repo(self):
        self.mock_session_repo.get_company_domain.return_value = 'empresa.waapp.co'
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.company.domain, 'empresa.waapp.co')

    def test_session_company_domain_is_none_when_not_configured(self):
        self.mock_session_repo.get_company_domain.return_value = None
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsNone(result.company.domain)

    def test_session_company_id_is_string(self):
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsInstance(result.company.id, str)

    def test_session_company_contains_nit(self):
        user = _make_user()
        user.company.nit = '800999111-2'

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.company.nit, '800999111-2')

    # ------------------------------------------------------------------
    # Suscripción
    # ------------------------------------------------------------------

    def test_session_includes_active_subscription(self):
        sub = _subscription(name='Enterprise', status='active')
        self.mock_session_repo.get_active_subscription.return_value = sub
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.company.subscription.name, 'Enterprise')
        self.assertEqual(result.company.subscription.status, 'active')

    def test_session_subscription_is_none_when_no_active_subscription(self):
        self.mock_session_repo.get_active_subscription.return_value = None
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertIsNone(result.company.subscription)

    def test_session_subscription_includes_end_date(self):
        sub = _subscription(end_date='2027-06-30')
        self.mock_session_repo.get_active_subscription.return_value = sub
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.company.subscription.end_date, '2027-06-30')

    # ------------------------------------------------------------------
    # Menú y features (permisos)
    # ------------------------------------------------------------------

    def test_session_includes_menu_items(self):
        menu = [_menu_item(code='orders'), _menu_item(code='picking', route='/warehouse/picking')]
        self.mock_session_repo.build_menu.return_value = (menu, [])
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(len(result.menu), 2)
        codes = [item.code for item in result.menu]
        self.assertIn('orders', codes)
        self.assertIn('picking', codes)

    def test_session_includes_feature_keys(self):
        features = ['warehouse.orders.view', 'warehouse.picking.create', 'billing.invoices.view']
        self.mock_session_repo.build_menu.return_value = ([], features)
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.features, features)

    def test_session_menu_is_empty_when_rol_has_no_modules(self):
        self.mock_session_repo.build_menu.return_value = ([], [])
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.menu, [])
        self.assertEqual(result.features, [])

    def test_build_menu_receives_user_rol_and_subscription_id(self):
        user = _make_user(rol_name='Supervisor')
        subscription = self.mock_session_repo.get_active_subscription.return_value

        self.use_case.execute(user, access=_FULL_ACCESS)

        self.mock_session_repo.build_menu.assert_called_once_with(
            user.rol, subscription.id, str(user.company.id),
        )

    # ------------------------------------------------------------------
    # Preferencias
    # ------------------------------------------------------------------

    def test_session_includes_user_preferences(self):
        prefs = _preferences(language='en', theme='dark')
        self.mock_session_repo.get_or_create_preferences.return_value = prefs
        user = _make_user()

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertEqual(result.user.preferences.language, 'en')
        self.assertEqual(result.user.preferences.theme, 'dark')

    def test_get_or_create_preferences_called_with_user(self):
        user = _make_user()

        self.use_case.execute(user, access=_FULL_ACCESS)

        self.mock_session_repo.get_or_create_preferences.assert_called_once_with(user)

    # ------------------------------------------------------------------
    # Llamadas al repositorio
    # ------------------------------------------------------------------

    def test_all_session_repository_methods_are_called(self):
        user = _make_user()

        self.use_case.execute(user, access=_FULL_ACCESS)

        self.mock_session_repo.get_company_domain.assert_called_once_with(user.company)
        self.mock_session_repo.get_or_create_preferences.assert_called_once_with(user)
        self.mock_session_repo.get_active_subscription.assert_called_once_with(user.company)
        subscription = self.mock_session_repo.get_active_subscription.return_value
        self.mock_session_repo.build_menu.assert_called_once_with(
            user.rol, subscription.id, str(user.company.id),
        )

    def test_each_user_gets_independent_session(self):
        user_a = _make_user()
        user_a.username = 'user_a'
        user_b = _make_user()
        user_b.username = 'user_b'

        self.mock_session_repo.build_menu.return_value = ([], [])

        session_a = self.use_case.execute(user_a, access=_FULL_ACCESS)
        session_b = self.use_case.execute(user_b, access=_FULL_ACCESS)

        self.assertEqual(session_a.user.username, 'user_a')
        self.assertEqual(session_b.user.username, 'user_b')

    def test_requires_policy_acceptance_when_pending(self):
        from platform.features.compliance.policy.policy.domain.enums import PolicyAudience
        from platform.features.compliance.policy.policy.domain.schemas import PendingPolicySchema

        user = _make_user()
        self.pending_mock.return_value = ([
            PendingPolicySchema(
                policy_id=uuid.uuid4(),
                code='PRIVACY-POLICY',
                name='Privacy',
                audience=PolicyAudience.CLIENT,
                country='CO',
                version=2,
                title='Privacy v2',
                content_hash='a' * 64,
                policy_country_id=uuid.uuid4(),
            ),
        ], 'CO')

        result = self.use_case.execute(user, access=_FULL_ACCESS)

        self.assertTrue(result.requires_policy_acceptance)
        self.assertEqual(result.policy_country, 'CO')

    def test_policy_check_failure_is_fail_closed(self):
        """Catalog errors must not silently bypass the policy gate."""
        user = _make_user()
        self.pending_mock.side_effect = RuntimeError('catalog down')

        with self.assertRaises(RuntimeError):
            self.use_case.execute(user, access=_FULL_ACCESS)

    def test_skips_policy_check_in_billing_recovery(self):
        user = _make_user()
        recovery = LoginAccessResult(mode='billing_recovery', subscription_status='suspended')
        self.mock_session_repo.build_billing_recovery_menu.return_value = ([], [])

        result = self.use_case.execute(user, access=recovery)

        self.assertFalse(result.requires_policy_acceptance)
        self.pending_mock.assert_not_called()
