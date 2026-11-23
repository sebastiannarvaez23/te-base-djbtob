"""
Unit tests for role constraint error scenarios:
  - ROLE_001 (ROLE_NOT_FOUND)      → NotFoundException propagada cuando el rol no existe
  - ROLE_002 (ROLE_DUPLICATE_NAME) → ConflictException propagada por nombre duplicado
  - ROLE_003 (ROLE_HAS_USERS)      → ConflictException propagada al eliminar rol con usuarios

Verifica que los use cases propagan correctamente las excepciones del repositorio
y que los códigos de error llevan el HTTP status esperado.

No se requiere base de datos.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from client.features.security.access.roles.application.use_cases import (
    CreateRoleUseCase,
    DeleteRoleUseCase,
    UpdateRoleFeaturesUseCase,
    UpdateRoleUseCase,
)
from client.features.security.access.roles.domain.schemas import (
    CreateRoleSchema,
    UpdateRoleFeaturesSchema,
    UpdateRoleSchema,
)
from core.errors.codes import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import AppException, ConflictException, NotFoundException, PermissionException


COMPANY_ID = uuid.uuid4()
ROLE_ID = uuid.uuid4()


# ── Registro de códigos de error ───────────────────────────────────────────────

class TestRoleErrorCodeRegistry(TestCase):

    def test_role_001_not_found_retorna_404(self):
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_NOT_FOUND]
        self.assertEqual(entry['http_status'], 404)
        self.assertEqual(AppErrorCode.ROLE_NOT_FOUND.value, 'ROLE_001')

    def test_role_002_duplicate_name_retorna_409(self):
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_DUPLICATE_NAME]
        self.assertEqual(entry['http_status'], 409)
        self.assertEqual(AppErrorCode.ROLE_DUPLICATE_NAME.value, 'ROLE_002')

    def test_role_003_has_users_retorna_409(self):
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_HAS_USERS]
        self.assertEqual(entry['http_status'], 409)
        self.assertEqual(AppErrorCode.ROLE_HAS_USERS.value, 'ROLE_003')

    def test_role_004_universal_not_editable_retorna_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE]
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE.value, 'ROLE_004')

    def test_role_001_002_003_004_tienen_valores_distintos(self):
        codes = {
            AppErrorCode.ROLE_NOT_FOUND,
            AppErrorCode.ROLE_DUPLICATE_NAME,
            AppErrorCode.ROLE_HAS_USERS,
            AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE,
        }
        self.assertEqual(len(codes), 4)


# ── ROLE_001: Rol no encontrado ────────────────────────────────────────────────

class TestRoleNotFoundError(TestCase):

    def test_update_role_inexistente_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleUseCase(mock_repo)
        mock_repo.update.side_effect = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='Nuevo nombre'))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_delete_role_inexistente_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = DeleteRoleUseCase(mock_repo)
        mock_repo.delete.side_effect = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_update_features_role_inexistente_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleFeaturesUseCase(mock_repo)
        mock_repo.update_features.side_effect = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleFeaturesSchema(feature_keys=[]))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)

    def test_not_found_exception_es_subclase_de_app_exception(self):
        exc = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        self.assertIsInstance(exc, AppException)

    def test_not_found_exception_lleva_detail_descriptivo(self):
        exc = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        self.assertIn('not exist', exc.detail.lower())
        self.assertEqual(exc.http_status, 404)

    def test_not_found_acepta_override_de_detail(self):
        role_id = uuid.uuid4()
        exc = NotFoundException(
            AppErrorCode.ROLE_NOT_FOUND,
            override_detail=f'El rol {role_id} no existe en esta empresa.',
        )
        self.assertIn(str(role_id), exc.detail)


# ── ROLE_002: Nombre de rol duplicado ─────────────────────────────────────────

class TestRoleDuplicateNameError(TestCase):

    def test_crear_rol_con_nombre_duplicado_propaga_conflict_exception(self):
        mock_repo = MagicMock()
        use_case = CreateRoleUseCase(mock_repo)
        mock_repo.create.side_effect = ConflictException(AppErrorCode.ROLE_DUPLICATE_NAME)

        data = CreateRoleSchema(name='Operador', company_id=COMPANY_ID)

        with self.assertRaises(ConflictException) as ctx:
            use_case.execute(data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_DUPLICATE_NAME)
        self.assertEqual(ctx.exception.http_status, 409)

    def test_renombrar_rol_a_nombre_existente_propaga_conflict_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleUseCase(mock_repo)
        mock_repo.update.side_effect = ConflictException(AppErrorCode.ROLE_DUPLICATE_NAME)

        with self.assertRaises(ConflictException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='Operador'))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_DUPLICATE_NAME)
        self.assertEqual(ctx.exception.http_status, 409)

    def test_duplicate_name_exception_es_subclase_de_app_exception(self):
        exc = ConflictException(AppErrorCode.ROLE_DUPLICATE_NAME)
        self.assertIsInstance(exc, AppException)

    def test_duplicate_name_exception_lleva_detail_descriptivo(self):
        exc = ConflictException(AppErrorCode.ROLE_DUPLICATE_NAME)
        self.assertIn('already exists', exc.detail.lower())

    def test_duplicate_name_exception_acepta_context(self):
        exc = ConflictException(
            AppErrorCode.ROLE_DUPLICATE_NAME,
            context={'name': 'Operador', 'company_id': str(COMPANY_ID)},
        )
        self.assertEqual(exc.context['name'], 'Operador')
        self.assertEqual(exc.context['company_id'], str(COMPANY_ID))


# ── ROLE_003: Rol con usuarios asignados ──────────────────────────────────────

class TestRoleHasUsersError(TestCase):

    def test_eliminar_rol_con_usuarios_propaga_conflict_exception(self):
        mock_repo = MagicMock()
        use_case = DeleteRoleUseCase(mock_repo)
        mock_repo.delete.side_effect = ConflictException(AppErrorCode.ROLE_HAS_USERS)

        with self.assertRaises(ConflictException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_HAS_USERS)
        self.assertEqual(ctx.exception.http_status, 409)

    def test_role_has_users_exception_es_subclase_de_app_exception(self):
        exc = ConflictException(AppErrorCode.ROLE_HAS_USERS)
        self.assertIsInstance(exc, AppException)

    def test_role_has_users_exception_lleva_detail_de_no_eliminable(self):
        exc = ConflictException(AppErrorCode.ROLE_HAS_USERS)
        self.assertIn('cannot be deleted', exc.detail.lower())
        self.assertEqual(exc.http_status, 409)

    def test_role_has_users_exception_puede_llevar_conteo_de_usuarios(self):
        exc = ConflictException(
            AppErrorCode.ROLE_HAS_USERS,
            context={'role_id': str(ROLE_ID), 'user_count': 5},
        )
        self.assertEqual(exc.context['user_count'], 5)
        self.assertEqual(exc.context['role_id'], str(ROLE_ID))

    def test_eliminar_rol_sin_usuarios_retorna_true(self):
        """Sanity check: la eliminación es exitosa cuando el rol no tiene usuarios."""
        mock_repo = MagicMock()
        use_case = DeleteRoleUseCase(mock_repo)
        mock_repo.delete.return_value = True

        result = use_case.execute(ROLE_ID, COMPANY_ID)

        self.assertTrue(result)
        mock_repo.delete.assert_called_once_with(ROLE_ID, COMPANY_ID)

    def test_role_003_es_distinto_de_role_002(self):
        """ROLE_003 (usuarios asignados) es un conflict diferente al de nombre duplicado."""
        self.assertNotEqual(AppErrorCode.ROLE_HAS_USERS, AppErrorCode.ROLE_DUPLICATE_NAME)
        exc_003 = ConflictException(AppErrorCode.ROLE_HAS_USERS)
        exc_002 = ConflictException(AppErrorCode.ROLE_DUPLICATE_NAME)
        self.assertNotEqual(exc_003.code, exc_002.code)
        self.assertEqual(exc_003.http_status, exc_002.http_status)  # ambos 409


# ── ROLE_004: Rol universal no editable por empresa ───────────────────────────

class TestRoleUniversalNotEditableError(TestCase):

    def test_update_rol_universal_propaga_permission_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleUseCase(mock_repo)
        mock_repo.update.side_effect = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)

        with self.assertRaises(PermissionException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='Nuevo nombre'))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    def test_update_features_rol_universal_propaga_permission_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleFeaturesUseCase(mock_repo)
        mock_repo.update_features.side_effect = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)

        with self.assertRaises(PermissionException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleFeaturesSchema(feature_keys=[]))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    def test_universal_not_editable_exception_es_subclase_de_app_exception(self):
        exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertIsInstance(exc, AppException)

    def test_universal_not_editable_exception_lleva_detail_descriptivo(self):
        exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertIn('platform', exc.detail.lower())
        self.assertEqual(exc.http_status, 403)

    def test_role_004_es_distinto_de_role_001_y_003(self):
        self.assertNotEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE, AppErrorCode.ROLE_NOT_FOUND)
        self.assertNotEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE, AppErrorCode.ROLE_HAS_USERS)
