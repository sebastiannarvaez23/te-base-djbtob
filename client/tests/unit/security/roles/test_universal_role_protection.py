"""
Unit tests para la protección de roles universales en DjangoRoleRepository:

  Capa de repositorio (con ORM mockeado):
    - update()         → NotFoundException    cuando el rol no existe (ROLE_001)
    - update()         → PermissionException  cuando el rol es universal (ROLE_004)
    - update()         → NotFoundException    cuando el rol pertenece a otra empresa (ROLE_001)
    - update()         → éxito               cuando el rol pertenece a la empresa
    - update_features() → NotFoundException   cuando el rol no existe (ROLE_001)
    - update_features() → PermissionException cuando el rol es universal (ROLE_004)
    - update_features() → NotFoundException   cuando el rol pertenece a otra empresa (ROLE_001)

  Capa de use cases (repositorio mockeado):
    - UpdateRoleUseCase         propaga PermissionException del repositorio
    - UpdateRoleFeaturesUseCase propaga PermissionException del repositorio
    - UpdateRoleUseCase         propaga NotFoundException del repositorio
    - Las excepciones son semánticamente distintas (403 vs 404)

No se requiere base de datos — el ORM de Django se reemplaza con mocks.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from client.features.security.access.roles.application.use_cases import (
    UpdateRoleFeaturesUseCase,
    UpdateRoleUseCase,
)
from client.features.security.access.roles.domain.schemas import (
    UpdateRoleFeaturesSchema,
    UpdateRoleSchema,
)
from client.features.security.access.roles.infrastructure.repositories import DjangoRoleRepository
from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException, NotFoundException, PermissionException


COMPANY_ID = uuid.uuid4()
OTHER_COMPANY_ID = uuid.uuid4()
ROLE_ID = uuid.uuid4()

_REPO_PATH = 'client.features.security.access.roles.infrastructure.repositories'


# ── Helpers ────────────────────────────────────────────────────────────────────

class _FakeDoesNotExist(Exception):
    """Sustituye Rol.DoesNotExist en los patches del ORM."""


def _mock_rol(company_id) -> MagicMock:
    """Devuelve un Rol mockeado con el company_id indicado."""
    rol = MagicMock()
    rol.id = ROLE_ID
    rol.name = 'Operador'
    rol.description = 'Rol de prueba'
    rol.is_active = True
    rol.company_id = company_id
    return rol


def _patch_rol(MockRol, company_id=None, not_found=False) -> MagicMock:
    """
    Configura MockRol.DoesNotExist y MockRol.objects.get con el comportamiento pedido.
    Devuelve el rol mockeado (o None si not_found).
    """
    MockRol.DoesNotExist = _FakeDoesNotExist
    if not_found:
        MockRol.objects.get.side_effect = _FakeDoesNotExist
        MockRol.objects.select_for_update.return_value.get.side_effect = _FakeDoesNotExist
        return None
    rol = _mock_rol(company_id)
    MockRol.objects.get.side_effect = None
    MockRol.objects.get.return_value = rol
    MockRol.objects.select_for_update.return_value.get.side_effect = None
    MockRol.objects.select_for_update.return_value.get.return_value = rol
    return rol


def _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess=None):
    """
    Configura los mocks de los querysets auxiliares que usa _to_schema.
    Devuelve una lista vacía de features y módulos para simplificar asserts.
    """
    MockRolFeature.objects.filter.return_value.values_list.return_value = []
    MockRolModule.objects.filter.return_value.values_list.return_value = []
    if MockCompanyRolAccess is not None:
        MockCompanyRolAccess.objects.get.side_effect = Exception('no access record')


# ── Repositorio: update() — casos de error ─────────────────────────────────────

class TestRepositoryUpdateErrorCases(TestCase):
    """
    Verifica que DjangoRoleRepository.update() lanza las excepciones correctas
    antes de tocar ninguna otra capa del ORM.
    """

    def setUp(self):
        self.repo = DjangoRoleRepository()
        self.data = UpdateRoleSchema(name='Nuevo nombre')

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_not_found_cuando_rol_no_existe(self, MockRol):
        _patch_rol(MockRol, not_found=True)

        with self.assertRaises(NotFoundException) as ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    @patch(f'{_REPO_PATH}.Rol')
    def test_not_found_exception_es_subclase_de_app_exception(self, MockRol):
        _patch_rol(MockRol, not_found=True)

        with self.assertRaises(AppException) as ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertIsInstance(ctx.exception, NotFoundException)

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_permission_exception_para_rol_universal(self, MockRol):
        _patch_rol(MockRol, company_id=None)

        with self.assertRaises(PermissionException) as ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    @patch(f'{_REPO_PATH}.Rol')
    def test_permission_exception_es_subclase_de_app_exception(self, MockRol):
        _patch_rol(MockRol, company_id=None)

        with self.assertRaises(AppException) as ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertIsInstance(ctx.exception, PermissionException)

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_not_found_cuando_rol_pertenece_a_otra_empresa(self, MockRol):
        _patch_rol(MockRol, company_id=OTHER_COMPANY_ID)

        with self.assertRaises(NotFoundException) as ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    @patch(f'{_REPO_PATH}.Rol')
    def test_not_found_y_permission_llevan_http_status_distintos(self, MockRol):
        """403 para rol universal, 404 para rol inexistente — no son intercambiables."""
        _patch_rol(MockRol, company_id=None)
        with self.assertRaises(PermissionException) as perm_ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        _patch_rol(MockRol, not_found=True)
        with self.assertRaises(NotFoundException) as nf_ctx:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)

        self.assertNotEqual(perm_ctx.exception.http_status, nf_ctx.exception.http_status)
        self.assertEqual(perm_ctx.exception.http_status, 403)
        self.assertEqual(nf_ctx.exception.http_status, 404)

    @patch(f'{_REPO_PATH}.Rol')
    def test_get_se_llama_con_solo_el_role_id_sin_filtro_de_company(self, MockRol):
        """
        Después del cambio, get() recibe únicamente id=role_id para poder
        distinguir "no existe" de "es universal".
        """
        _patch_rol(MockRol, company_id=None)

        try:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)
        except PermissionException:
            pass

        MockRol.objects.get.assert_called_once_with(id=ROLE_ID)

    @patch(f'{_REPO_PATH}.Rol')
    def test_update_no_se_llama_para_rol_universal(self, MockRol):
        """No debe persistirse nada si el rol es universal."""
        rol = _patch_rol(MockRol, company_id=None)

        try:
            self.repo.update(ROLE_ID, COMPANY_ID, self.data)
        except PermissionException:
            pass

        if rol:
            rol.save.assert_not_called()


# ── Repositorio: update() — caso exitoso ───────────────────────────────────────

class TestRepositoryUpdateSuccess(TestCase):
    """
    Verifica que update() completa correctamente cuando el rol pertenece
    a la empresa que realiza la petición.
    """

    def setUp(self):
        self.repo = DjangoRoleRepository()

    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Rol')
    def test_actualiza_nombre_y_persiste(self, MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess):
        rol = _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)

        self.repo.update(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='Actualizado'))

        self.assertEqual(rol.name, 'Actualizado')
        rol.save.assert_called_once()

    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Rol')
    def test_actualiza_descripcion_y_persiste(self, MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess):
        rol = _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)

        self.repo.update(ROLE_ID, COMPANY_ID, UpdateRoleSchema(description='Nueva desc'))

        self.assertEqual(rol.description, 'Nueva desc')
        rol.save.assert_called_once()

    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Rol')
    def test_retorna_schema_con_is_generic_false(self, MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess):
        _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)

        result = self.repo.update(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='X'))

        self.assertFalse(result.is_generic)
        self.assertTrue(result.is_editable)

    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Rol')
    def test_actualiza_estado_activo(self, MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess):
        rol = _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)

        self.repo.update(ROLE_ID, COMPANY_ID, UpdateRoleSchema(is_active=False))

        self.assertFalse(rol.is_active)
        rol.save.assert_called_once()


# ── Repositorio: update_features() — casos de error ───────────────────────────

class TestRepositoryUpdateFeaturesErrorCases(TestCase):
    """
    Verifica que DjangoRoleRepository.update_features() lanza las excepciones
    correctas, con la misma lógica de protección que update().
    """

    def setUp(self):
        self.repo = DjangoRoleRepository()
        self.data = UpdateRoleFeaturesSchema(feature_keys=['orders.view'])

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_not_found_cuando_rol_no_existe(self, MockRol):
        _patch_rol(MockRol, not_found=True)

        with self.assertRaises(NotFoundException) as ctx:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_permission_exception_para_rol_universal(self, MockRol):
        _patch_rol(MockRol, company_id=None)

        with self.assertRaises(PermissionException) as ctx:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    @patch(f'{_REPO_PATH}.Rol')
    def test_lanza_not_found_cuando_rol_pertenece_a_otra_empresa(self, MockRol):
        _patch_rol(MockRol, company_id=OTHER_COMPANY_ID)

        with self.assertRaises(NotFoundException) as ctx:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    @patch(f'{_REPO_PATH}.Rol')
    def test_get_se_llama_con_solo_el_role_id_sin_filtro_de_company(self, MockRol):
        _patch_rol(MockRol, company_id=None)

        try:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)
        except PermissionException:
            pass

        MockRol.objects.get.assert_called_once_with(id=ROLE_ID)

    @patch(f'{_REPO_PATH}.Rol')
    def test_permission_exception_y_not_found_tienen_http_status_distintos(self, MockRol):
        _patch_rol(MockRol, company_id=None)
        with self.assertRaises(PermissionException) as perm_ctx:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)

        _patch_rol(MockRol, not_found=True)
        with self.assertRaises(NotFoundException) as nf_ctx:
            self.repo.update_features(ROLE_ID, COMPANY_ID, self.data)

        self.assertEqual(perm_ctx.exception.http_status, 403)
        self.assertEqual(nf_ctx.exception.http_status, 404)


# ── Repositorio: update_features() — caso exitoso ─────────────────────────────

class TestRepositoryUpdateFeaturesSuccess(TestCase):

    def setUp(self):
        self.repo = DjangoRoleRepository()

    @patch(f'{_REPO_PATH}.transaction.atomic')
    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Functionality')
    @patch(f'{_REPO_PATH}.Rol')
    def test_reemplaza_features_para_rol_de_la_empresa(
        self, MockRol, MockFunctionality, MockRolFeature, MockRolModule, MockCompanyRolAccess, _atomic
    ):
        _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)
        MockFunctionality.objects.filter.return_value = []
        _atomic.return_value.__exit__.return_value = False

        data = UpdateRoleFeaturesSchema(feature_keys=['orders.view', 'orders.create'])
        result = self.repo.update_features(ROLE_ID, COMPANY_ID, data)

        self.assertIsNotNone(result)
        MockRolFeature.objects.filter.return_value.delete.assert_called()

    @patch(f'{_REPO_PATH}.transaction.atomic')
    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Functionality')
    @patch(f'{_REPO_PATH}.Rol')
    def test_retorna_schema_con_is_generic_false(
        self, MockRol, MockFunctionality, MockRolFeature, MockRolModule, MockCompanyRolAccess, _atomic
    ):
        _patch_rol(MockRol, company_id=COMPANY_ID)
        _configure_schema_mocks(MockRol, MockRolFeature, MockRolModule, MockCompanyRolAccess)
        MockFunctionality.objects.filter.return_value = []
        _atomic.return_value.__exit__.return_value = False

        result = self.repo.update_features(ROLE_ID, COMPANY_ID, UpdateRoleFeaturesSchema(feature_keys=[]))

        self.assertFalse(result.is_generic)
        self.assertTrue(result.is_editable)

    @patch(f'{_REPO_PATH}.transaction.atomic')
    @patch(f'{_REPO_PATH}.CompanyRolAccess')
    @patch(f'{_REPO_PATH}.RolModule')
    @patch(f'{_REPO_PATH}.RolFeature')
    @patch(f'{_REPO_PATH}.Functionality')
    @patch(f'{_REPO_PATH}.Rol')
    def test_un_fallo_al_insertar_permanece_dentro_de_la_transaccion(
        self, MockRol, MockFunctionality, MockRolFeature, MockRolModule, MockCompanyRolAccess, mock_atomic,
    ):
        _patch_rol(MockRol, company_id=COMPANY_ID)
        feature = MagicMock()
        feature.offering = 'plan'
        MockFunctionality.objects.filter.return_value = [feature]
        events = []
        mock_atomic.return_value.__enter__.side_effect = lambda: events.append('begin')

        def _exit(exc_type, exc, tb):
            events.append(exc_type)
            return False

        mock_atomic.return_value.__exit__.side_effect = _exit
        MockRolFeature.objects.filter.return_value.delete.side_effect = lambda: events.append('delete')
        MockRolFeature.objects.bulk_create.side_effect = RuntimeError('insert failed')

        with self.assertRaises(RuntimeError):
            self.repo.update_features(
                ROLE_ID,
                COMPANY_ID,
                UpdateRoleFeaturesSchema(feature_keys=['orders.view']),
            )

        self.assertEqual(events, ['begin', 'delete', RuntimeError])


# ── Use cases: propagación de excepciones ─────────────────────────────────────

class TestUseCasePropagatesPermissionException(TestCase):
    """
    Verifica que los use cases no absorben las excepciones del repositorio.
    El repositorio está mockeado — se prueba solo la capa de aplicación.
    """

    def test_update_role_propaga_permission_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleUseCase(mock_repo)
        mock_repo.update.side_effect = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)

        with self.assertRaises(PermissionException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='X'))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    def test_update_features_propaga_permission_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleFeaturesUseCase(mock_repo)
        mock_repo.update_features.side_effect = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)

        with self.assertRaises(PermissionException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleFeaturesSchema(feature_keys=[]))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(ctx.exception.http_status, 403)

    def test_update_role_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleUseCase(mock_repo)
        mock_repo.update.side_effect = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleSchema(name='X'))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_update_features_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateRoleFeaturesUseCase(mock_repo)
        mock_repo.update_features.side_effect = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(ROLE_ID, COMPANY_ID, UpdateRoleFeaturesSchema(feature_keys=[]))

        self.assertEqual(ctx.exception.code, AppErrorCode.ROLE_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_permission_exception_no_es_not_found(self):
        perm_exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        nf_exc = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        self.assertNotIsInstance(perm_exc, NotFoundException)
        self.assertNotEqual(perm_exc.code, nf_exc.code)

    def test_permission_exception_tiene_403_y_not_found_tiene_404(self):
        perm_exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        nf_exc = NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        self.assertEqual(perm_exc.http_status, 403)
        self.assertEqual(nf_exc.http_status, 404)


# ── Semántica: ROLE_004 en el registro de errores ─────────────────────────────

class TestRole004ErrorRegistry(TestCase):
    """
    Verifica que ROLE_004 está correctamente registrado y su semántica
    es coherente con el dominio (403, mensaje descriptivo, distinto de los otros).
    """
    from core.errors.codes import ERROR_REGISTRY

    def test_role_004_tiene_http_status_403(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE]
        self.assertEqual(entry['http_status'], 403)

    def test_role_004_message_indica_no_editable(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE]
        self.assertIn('not editable', entry['message'].lower())

    def test_role_004_detail_menciona_plataforma(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE]
        self.assertIn('platform', entry['detail'].lower())

    def test_role_004_es_distinto_de_role_001(self):
        self.assertNotEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE, AppErrorCode.ROLE_NOT_FOUND)

    def test_role_004_es_distinto_de_role_002(self):
        self.assertNotEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE, AppErrorCode.ROLE_DUPLICATE_NAME)

    def test_role_004_es_distinto_de_role_003(self):
        self.assertNotEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE, AppErrorCode.ROLE_HAS_USERS)

    def test_role_004_tiene_valor_string_correcto(self):
        self.assertEqual(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE.value, 'ROLE_004')

    def test_permission_exception_con_role_004_lleva_403(self):
        exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertEqual(exc.http_status, 403)
        self.assertEqual(exc.code, AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)

    def test_permission_exception_con_role_004_tiene_detail_descriptivo(self):
        exc = PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        self.assertTrue(len(exc.detail) > 0)
        self.assertIn('platform', exc.detail.lower())

    def test_permission_exception_acepta_override_de_detail(self):
        rol_id = uuid.uuid4()
        exc = PermissionException(
            AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE,
            override_detail=f'El rol {rol_id} es universal y no puede ser modificado.',
        )
        self.assertIn(str(rol_id), exc.detail)

    def test_permission_exception_acepta_context(self):
        exc = PermissionException(
            AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE,
            context={'role_id': str(ROLE_ID), 'company_id': str(COMPANY_ID)},
        )
        self.assertEqual(exc.context['role_id'], str(ROLE_ID))
        self.assertEqual(exc.context['company_id'], str(COMPANY_ID))
