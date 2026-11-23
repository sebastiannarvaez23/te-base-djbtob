"""
Unit tests para permisos a nivel de usuario (capa de rol):
  - PERM_001 (PERM_INSUFFICIENT)        → permisos insuficientes para la acción
  - PERM_002 (PERM_FEATURE_NOT_ALLOWED) → funcionalidad no habilitada en el rol del usuario
  - PermissionException lleva código, HTTP status y detail correctos
  - IsCompanyMember bloquea usuarios sin empresa asignada

Diferencia clave con SUB_*: los errores PERM_* ocurren a nivel de rol de usuario,
ANTES de que se evalúe si la suscripción del plan incluye la funcionalidad.

No se requiere base de datos ni Redis.
"""
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors.codes import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import AppException, PermissionException, SubscriptionException
from core.permissions import IsCompanyMember


# ── Registro de códigos de error ───────────────────────────────────────────────

class TestPermissionErrorCodeRegistry(TestCase):

    def test_perm_001_insufficient_retorna_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.PERM_INSUFFICIENT]
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(AppErrorCode.PERM_INSUFFICIENT.value, 'PERM_001')

    def test_perm_002_feature_not_allowed_retorna_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.PERM_FEATURE_NOT_ALLOWED]
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(AppErrorCode.PERM_FEATURE_NOT_ALLOWED.value, 'PERM_002')

    def test_perm_001_message_indica_falta_de_permisos(self):
        entry = ERROR_REGISTRY[AppErrorCode.PERM_INSUFFICIENT]
        self.assertIn('permission', entry['message'].lower())

    def test_perm_002_message_indica_feature_restringida(self):
        entry = ERROR_REGISTRY[AppErrorCode.PERM_FEATURE_NOT_ALLOWED]
        self.assertIn('feature', entry['message'].lower())

    def test_perm_001_y_002_tienen_valores_distintos(self):
        self.assertNotEqual(
            AppErrorCode.PERM_INSUFFICIENT,
            AppErrorCode.PERM_FEATURE_NOT_ALLOWED,
        )

    def test_perm_001_y_002_tienen_valores_de_cadena_correctos(self):
        self.assertEqual(AppErrorCode.PERM_INSUFFICIENT.value, 'PERM_001')
        self.assertEqual(AppErrorCode.PERM_FEATURE_NOT_ALLOWED.value, 'PERM_002')


# ── PermissionException: PERM_001 — Permisos insuficientes ────────────────────

class TestPermissionExceptionPerm001(TestCase):

    def test_crea_excepcion_con_codigo_correcto(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertEqual(exc.code, AppErrorCode.PERM_INSUFFICIENT)

    def test_http_status_es_403(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertEqual(exc.http_status, 403)

    def test_detail_describe_falta_de_permisos(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertIn('permission', exc.detail.lower())

    def test_es_subclase_de_app_exception(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertIsInstance(exc, AppException)

    def test_no_es_subscription_exception(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertNotIsInstance(exc, SubscriptionException)

    def test_override_detail_reemplaza_default(self):
        exc = PermissionException(
            AppErrorCode.PERM_INSUFFICIENT,
            override_detail='Solo los supervisores pueden aprobar transferencias.',
        )
        self.assertEqual(exc.detail, 'Solo los supervisores pueden aprobar transferencias.')

    def test_context_almacena_datos_de_rol_requerido(self):
        exc = PermissionException(
            AppErrorCode.PERM_INSUFFICIENT,
            context={'required_role': 'manager', 'user_role': 'operator'},
        )
        self.assertEqual(exc.context['required_role'], 'manager')
        self.assertEqual(exc.context['user_role'], 'operator')

    def test_context_vacio_por_defecto(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertEqual(exc.context, {})

    def test_mensaje_accesible_desde_la_excepcion(self):
        exc = PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        self.assertIsNotNone(exc.message)
        self.assertIsInstance(exc.message, str)


# ── PermissionException: PERM_002 — Feature no habilitada en el rol ───────────

class TestPermissionExceptionPerm002(TestCase):

    def test_crea_excepcion_con_codigo_correcto(self):
        exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        self.assertEqual(exc.code, AppErrorCode.PERM_FEATURE_NOT_ALLOWED)

    def test_http_status_es_403(self):
        exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        self.assertEqual(exc.http_status, 403)

    def test_detail_menciona_restriccion_de_rol(self):
        exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        self.assertIn('role', exc.detail.lower())

    def test_es_subclase_de_app_exception(self):
        exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        self.assertIsInstance(exc, AppException)

    def test_context_almacena_feature_key(self):
        exc = PermissionException(
            AppErrorCode.PERM_FEATURE_NOT_ALLOWED,
            context={'feature_key': 'warehouse.orders.approve'},
        )
        self.assertEqual(exc.context['feature_key'], 'warehouse.orders.approve')

    def test_perm_002_y_sub_002_tienen_mismo_status_pero_distinto_codigo(self):
        """PERM_002 es restricción por rol; SUB_002 es restricción por plan.
        Ambas retornan 403, pero representan capas de acceso distintas."""
        perm_exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        sub_exc = SubscriptionException(AppErrorCode.SUB_FEATURE_DENIED)
        self.assertEqual(perm_exc.http_status, sub_exc.http_status)
        self.assertNotEqual(perm_exc.code, sub_exc.code)

    def test_override_detail_reemplaza_default(self):
        exc = PermissionException(
            AppErrorCode.PERM_FEATURE_NOT_ALLOWED,
            override_detail='Tu rol no tiene acceso a la aprobación de pedidos.',
        )
        self.assertIn('aprobación', exc.detail)

    def test_excepcion_es_string_de_su_detail(self):
        exc = PermissionException(AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
        self.assertEqual(str(exc), exc.detail)


# ── IsCompanyMember: control de acceso por empresa ────────────────────────────

class TestIsCompanyMemberPermission(TestCase):
    """IsCompanyMember es la primera línea de defensa para vistas de empresa.
    Bloquea cualquier request donde el usuario no pertenezca a un tenant."""

    def setUp(self):
        self.permission = IsCompanyMember()

    def _request_with_company(self, company_id=None):
        import uuid
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.company_id = company_id or uuid.uuid4()
        return request

    def test_usuario_autenticado_con_empresa_tiene_acceso(self):
        request = self._request_with_company()
        result = self.permission.has_permission(request, MagicMock())
        self.assertTrue(result)

    def test_usuario_no_autenticado_es_denegado(self):
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        request.user.company_id = None

        result = self.permission.has_permission(request, MagicMock())

        self.assertFalse(result)

    def test_usuario_autenticado_sin_company_id_es_denegado(self):
        """company_id = None → usuario sin empresa asignada → acceso denegado."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.company_id = None

        result = self.permission.has_permission(request, MagicMock())

        self.assertFalse(result)

    def test_usuario_sin_atributo_company_id_es_denegado(self):
        """hasattr devuelve False si el modelo de usuario no tiene company_id."""
        request = MagicMock()
        request.user = MagicMock(spec=['is_authenticated'])
        request.user.is_authenticated = True

        result = self.permission.has_permission(request, MagicMock())

        self.assertFalse(result)

    def test_request_sin_usuario_es_denegado(self):
        """request.user = None → cortocircuito → denegado."""
        request = MagicMock()
        request.user = None

        result = self.permission.has_permission(request, MagicMock())

        self.assertFalse(result)

    def test_company_id_con_uuid_valido_pasa(self):
        import uuid
        company_id = uuid.uuid4()
        request = self._request_with_company(company_id=company_id)
        result = self.permission.has_permission(request, MagicMock())
        self.assertTrue(result)

    def test_evaluacion_es_independiente_de_la_vista(self):
        """El permiso no depende de atributos específicos de la vista."""
        request = self._request_with_company()
        view_a = MagicMock()
        view_b = MagicMock()
        result_a = self.permission.has_permission(request, view_a)
        result_b = self.permission.has_permission(request, view_b)
        self.assertTrue(result_a)
        self.assertTrue(result_b)

    def test_usuario_de_una_empresa_no_accede_como_otra(self):
        """Usuarios de distintas empresas tienen company_id distintos."""
        import uuid
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        request_a = self._request_with_company(company_id=company_a)
        request_b = self._request_with_company(company_id=company_b)

        result_a = self.permission.has_permission(request_a, MagicMock())
        result_b = self.permission.has_permission(request_b, MagicMock())

        self.assertTrue(result_a)
        self.assertTrue(result_b)
        self.assertNotEqual(
            request_a.user.company_id,
            request_b.user.company_id,
        )
