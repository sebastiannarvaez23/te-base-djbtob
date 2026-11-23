"""
Unit tests for authentication blocked scenarios:
  - AUTH_002 (AUTH_ROLE_DISABLED)     → el rol del usuario está deshabilitado
  - AUTH_006 (AUTH_COMPANY_SUSPENDED) → la empresa del usuario está suspendida

Verifica que:
  - LoginUserUseCase propaga AuthException correctamente desde el repositorio
  - El token no se emite cuando la autenticación falla
  - Los objetos de excepción llevan el HTTP status y código correctos

No se requiere base de datos.
"""
from unittest import TestCase
from unittest.mock import MagicMock

from client.features.security.lifecycle.auth.application.use_cases import LoginUserUseCase
from core.errors.codes import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import AppException, AuthException


# ── Registro de códigos de error ───────────────────────────────────────────────

class TestAuthBlockedErrorCodeRegistry(TestCase):

    def test_auth_002_role_disabled_retorna_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ROLE_DISABLED]
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(AppErrorCode.AUTH_ROLE_DISABLED.value, 'AUTH_002')

    def test_auth_006_company_suspended_retorna_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_COMPANY_SUSPENDED]
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(AppErrorCode.AUTH_COMPANY_SUSPENDED.value, 'AUTH_006')

    def test_auth_002_message_indica_rol_deshabilitado(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ROLE_DISABLED]
        self.assertIn('disabled', entry['message'].lower())

    def test_auth_006_message_indica_empresa_suspendida(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_COMPANY_SUSPENDED]
        self.assertIn('suspended', entry['message'].lower())

    def test_auth_002_y_006_tienen_codigos_distintos(self):
        self.assertNotEqual(
            AppErrorCode.AUTH_ROLE_DISABLED,
            AppErrorCode.AUTH_COMPANY_SUSPENDED,
        )

    def test_auth_002_y_006_tienen_valores_de_cadena_correctos(self):
        self.assertEqual(AppErrorCode.AUTH_ROLE_DISABLED.value, 'AUTH_002')
        self.assertEqual(AppErrorCode.AUTH_COMPANY_SUSPENDED.value, 'AUTH_006')


# ── AUTH_002: Rol del usuario deshabilitado ────────────────────────────────────

class TestRoleDisabledScenario(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = LoginUserUseCase(self.mock_repo)

    def test_login_propaga_auth_exception_cuando_rol_esta_deshabilitado(self):
        self.mock_repo.authenticate.side_effect = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)

        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ROLE_DISABLED)

    def test_role_disabled_exception_tiene_status_403(self):
        exc = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        self.assertEqual(exc.http_status, 403)

    def test_role_disabled_exception_lleva_detail_descriptivo(self):
        exc = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        self.assertIn('disabled', exc.detail.lower())

    def test_token_no_se_emite_cuando_rol_esta_deshabilitado(self):
        """El repositorio lanza AuthException antes de que se solicite el token."""
        self.mock_repo.authenticate.side_effect = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)

        with self.assertRaises(AuthException):
            self.use_case.execute('jsmith', 'pass1234')

        self.mock_repo.get_or_create_token.assert_not_called()

    def test_role_disabled_exception_es_subclase_de_app_exception(self):
        exc = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        self.assertIsInstance(exc, AppException)

    def test_role_disabled_acepta_override_de_detail(self):
        exc = AuthException(
            AppErrorCode.AUTH_ROLE_DISABLED,
            override_detail='El rol "Operador" está desactivado. Contacta al administrador.',
        )
        self.assertIn('Operador', exc.detail)

    def test_role_disabled_acepta_context_con_rol_id(self):
        import uuid
        role_id = uuid.uuid4()
        exc = AuthException(
            AppErrorCode.AUTH_ROLE_DISABLED,
            context={'role_id': str(role_id), 'role_name': 'Operador'},
        )
        self.assertEqual(exc.context['role_name'], 'Operador')
        self.assertEqual(exc.context['role_id'], str(role_id))


# ── AUTH_006: Empresa del usuario suspendida ───────────────────────────────────

class TestCompanySuspendedScenario(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = LoginUserUseCase(self.mock_repo)

    def test_login_propaga_auth_exception_cuando_empresa_esta_suspendida(self):
        self.mock_repo.authenticate.side_effect = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)

        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_SUSPENDED)

    def test_company_suspended_exception_tiene_status_403(self):
        exc = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertEqual(exc.http_status, 403)

    def test_company_suspended_exception_lleva_detail_descriptivo(self):
        exc = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertIn('suspended', exc.detail.lower())

    def test_token_no_se_emite_cuando_empresa_esta_suspendida(self):
        """El repositorio lanza AuthException antes de que se solicite el token."""
        self.mock_repo.authenticate.side_effect = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)

        with self.assertRaises(AuthException):
            self.use_case.execute('jsmith', 'pass1234')

        self.mock_repo.get_or_create_token.assert_not_called()

    def test_company_suspended_exception_es_subclase_de_app_exception(self):
        exc = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertIsInstance(exc, AppException)

    def test_company_suspended_acepta_context_con_company_id(self):
        import uuid
        company_id = uuid.uuid4()
        exc = AuthException(
            AppErrorCode.AUTH_COMPANY_SUSPENDED,
            context={'company_id': str(company_id), 'company_name': 'Bodega Central'},
        )
        self.assertEqual(exc.context['company_name'], 'Bodega Central')
        self.assertEqual(exc.context['company_id'], str(company_id))


# ── Comparación entre escenarios bloqueados ────────────────────────────────────

class TestAuthBlockedScenariosComparison(TestCase):

    def test_ambos_escenarios_retornan_403(self):
        role_disabled = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        company_suspended = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertEqual(role_disabled.http_status, 403)
        self.assertEqual(company_suspended.http_status, 403)

    def test_ambos_escenarios_tienen_codigos_distintos(self):
        role_disabled = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        company_suspended = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertNotEqual(role_disabled.code, company_suspended.code)

    def test_ambos_escenarios_son_auth_exception(self):
        role_disabled = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        company_suspended = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertIsInstance(role_disabled, AuthException)
        self.assertIsInstance(company_suspended, AuthException)

    def test_auth_002_difiere_de_auth_001_invalid_credentials(self):
        """AUTH_002 (403) y AUTH_001 (401) representan errores de acceso distintos."""
        role_disabled = AuthException(AppErrorCode.AUTH_ROLE_DISABLED)
        invalid_creds = AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)
        self.assertNotEqual(role_disabled.code, invalid_creds.code)
        self.assertNotEqual(role_disabled.http_status, invalid_creds.http_status)

    def test_auth_006_difiere_de_auth_003_account_inactive(self):
        """AUTH_006 (empresa suspendida) y AUTH_003 (cuenta inactiva) son escenarios distintos."""
        company_suspended = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        account_inactive = AuthException(AppErrorCode.AUTH_ACCOUNT_INACTIVE)
        self.assertNotEqual(company_suspended.code, account_inactive.code)
        self.assertEqual(company_suspended.http_status, account_inactive.http_status)  # ambos 403
