"""
Unit tests para errores de restricción en topes de suscripción:
  - SLIMIT_001 (SLIMIT_NOT_FOUND) → NotFoundException cuando el tope no existe
  - SLIMIT_002 (SLIMIT_DUPLICATE) → ConflictException al crear tope duplicado

Verifica que los use cases propagan correctamente las excepciones del repositorio
y que los códigos de error llevan el HTTP status esperado.

No se requiere base de datos.
"""
import uuid
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.billing.subscription.subscription_limit.application.use_cases import (
    CreateSubscriptionLimitUseCase,
    DeleteSubscriptionLimitUseCase,
    GetSubscriptionLimitByIdUseCase,
    UpdateSubscriptionLimitUseCase,
)
from platform.features.billing.subscription.subscription_limit.domain.schemas import (
    CreateSubscriptionLimitSchema,
    SubscriptionLimitSchema,
    UpdateSubscriptionLimitSchema,
)
from core.errors.codes import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import AppException, ConflictException, NotFoundException


# ── Helper ─────────────────────────────────────────────────────────────────────

def _limit(**overrides) -> SubscriptionLimitSchema:
    defaults = dict(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        functionality_id=uuid.uuid4(),
        subscription_name='Plan Profesional',
        functionality_key='orders.create',
        functionality_label='Crear Pedidos',
        functionality_module_code='orders',
        name='Tope de Pedidos',
        max_value=1000,
        validation_type='lifetime',
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return SubscriptionLimitSchema(**defaults)


# ── Registro de códigos de error ───────────────────────────────────────────────

class TestSubscriptionLimitErrorCodeRegistry(TestCase):

    def test_slimit_001_not_found_retorna_404(self):
        entry = ERROR_REGISTRY[AppErrorCode.SLIMIT_NOT_FOUND]
        self.assertEqual(entry['http_status'], 404)
        self.assertEqual(AppErrorCode.SLIMIT_NOT_FOUND.value, 'SLIMIT_001')

    def test_slimit_002_duplicate_retorna_409(self):
        entry = ERROR_REGISTRY[AppErrorCode.SLIMIT_DUPLICATE]
        self.assertEqual(entry['http_status'], 409)
        self.assertEqual(AppErrorCode.SLIMIT_DUPLICATE.value, 'SLIMIT_002')

    def test_slimit_001_message_indica_no_encontrado(self):
        entry = ERROR_REGISTRY[AppErrorCode.SLIMIT_NOT_FOUND]
        self.assertIn('not found', entry['message'].lower())

    def test_slimit_002_message_indica_duplicado(self):
        entry = ERROR_REGISTRY[AppErrorCode.SLIMIT_DUPLICATE]
        self.assertIn('duplicate', entry['message'].lower())

    def test_slimit_001_y_002_tienen_valores_distintos(self):
        self.assertNotEqual(AppErrorCode.SLIMIT_NOT_FOUND, AppErrorCode.SLIMIT_DUPLICATE)

    def test_slimit_001_y_002_tienen_valores_de_cadena_correctos(self):
        self.assertEqual(AppErrorCode.SLIMIT_NOT_FOUND.value, 'SLIMIT_001')
        self.assertEqual(AppErrorCode.SLIMIT_DUPLICATE.value, 'SLIMIT_002')


# ── SLIMIT_001: Tope de suscripción no encontrado ─────────────────────────────

class TestSubscriptionLimitNotFoundError(TestCase):

    def test_get_by_id_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = GetSubscriptionLimitByIdUseCase(mock_repo)
        mock_repo.get_by_id.side_effect = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(uuid.uuid4())

        self.assertEqual(ctx.exception.code, AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_update_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = UpdateSubscriptionLimitUseCase(mock_repo)
        mock_repo.get_by_id.return_value = None

        result = use_case.execute(uuid.uuid4(), UpdateSubscriptionLimitSchema(max_value=500))

        self.assertIsNone(result)
        mock_repo.update.assert_not_called()

    def test_update_propaga_not_found_si_repo_update_lanza(self):
        mock_repo = MagicMock()
        use_case = UpdateSubscriptionLimitUseCase(mock_repo)
        mock_repo.get_by_id.return_value = _limit()
        mock_repo.update.side_effect = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(uuid.uuid4(), UpdateSubscriptionLimitSchema(max_value=500))

        self.assertEqual(ctx.exception.code, AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_delete_propaga_not_found_exception(self):
        mock_repo = MagicMock()
        use_case = DeleteSubscriptionLimitUseCase(mock_repo)
        mock_repo.delete.side_effect = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)

        with self.assertRaises(NotFoundException) as ctx:
            use_case.execute(uuid.uuid4())

        self.assertEqual(ctx.exception.code, AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_not_found_exception_es_subclase_de_app_exception(self):
        exc = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertIsInstance(exc, AppException)

    def test_not_found_exception_lleva_detail_descriptivo(self):
        exc = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertIn('not exist', exc.detail.lower())

    def test_not_found_acepta_override_de_detail(self):
        limit_id = uuid.uuid4()
        exc = NotFoundException(
            AppErrorCode.SLIMIT_NOT_FOUND,
            override_detail=f'El tope con id={limit_id} no existe.',
        )
        self.assertIn(str(limit_id), exc.detail)

    def test_get_by_id_retorna_none_cuando_repo_devuelve_none(self):
        """Repositorio devuelve None (sin excepción): el use case lo propaga tal cual."""
        mock_repo = MagicMock()
        use_case = GetSubscriptionLimitByIdUseCase(mock_repo)
        mock_repo.get_by_id.return_value = None

        result = use_case.execute(uuid.uuid4())

        self.assertIsNone(result)


# ── SLIMIT_002: Tope de suscripción duplicado ──────────────────────────────────

class TestSubscriptionLimitDuplicateError(TestCase):

    def _create_data(self, sub_id=None, func_id=None) -> CreateSubscriptionLimitSchema:
        return CreateSubscriptionLimitSchema(
            subscription_id=sub_id or uuid.uuid4(),
            functionality_id=func_id or uuid.uuid4(),
            max_value=100,
        )

    def test_crear_tope_duplicado_propaga_conflict_exception(self):
        from django.db import IntegrityError

        mock_repo = MagicMock()
        use_case = CreateSubscriptionLimitUseCase(mock_repo)
        mock_repo.create.side_effect = IntegrityError('unique')

        with self.assertRaises(ConflictException) as ctx:
            use_case.execute(self._create_data())

        self.assertEqual(ctx.exception.code, AppErrorCode.SLIMIT_DUPLICATE)
        self.assertEqual(ctx.exception.http_status, 409)

    def test_duplicate_exception_es_subclase_de_app_exception(self):
        exc = ConflictException(AppErrorCode.SLIMIT_DUPLICATE)
        self.assertIsInstance(exc, AppException)

    def test_duplicate_exception_lleva_detail_descriptivo(self):
        exc = ConflictException(AppErrorCode.SLIMIT_DUPLICATE)
        self.assertIn('already exists', exc.detail.lower())
        self.assertEqual(exc.http_status, 409)

    def test_duplicate_exception_puede_llevar_context_con_ids(self):
        sub_id = uuid.uuid4()
        func_id = uuid.uuid4()
        exc = ConflictException(
            AppErrorCode.SLIMIT_DUPLICATE,
            context={'subscription_id': str(sub_id), 'functionality_id': str(func_id)},
        )
        self.assertEqual(exc.context['subscription_id'], str(sub_id))
        self.assertEqual(exc.context['functionality_id'], str(func_id))

    def test_slimit_duplicate_difiere_de_slimit_not_found(self):
        exc_dup = ConflictException(AppErrorCode.SLIMIT_DUPLICATE)
        exc_nf = NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND)
        self.assertNotEqual(exc_dup.code, exc_nf.code)
        self.assertNotEqual(exc_dup.http_status, exc_nf.http_status)

    def test_crear_tope_para_distinta_suscripcion_misma_funcionalidad_es_valido(self):
        """Dos suscripciones diferentes pueden tener topes para la misma funcionalidad."""
        mock_repo = MagicMock()
        use_case = CreateSubscriptionLimitUseCase(mock_repo)

        sub1_id = uuid.uuid4()
        func_id = uuid.uuid4()
        created = _limit(subscription_id=sub1_id, functionality_id=func_id)
        mock_repo.create.return_value = created

        data = self._create_data(sub_id=sub1_id, func_id=func_id)
        result = use_case.execute(data)

        self.assertIsNotNone(result)
        self.assertEqual(result.subscription_id, sub1_id)

    def test_crear_tope_para_distinta_funcionalidad_misma_suscripcion_es_valido(self):
        """Una suscripción puede tener topes para múltiples funcionalidades distintas."""
        mock_repo = MagicMock()
        use_case = CreateSubscriptionLimitUseCase(mock_repo)

        sub_id = uuid.uuid4()
        func_a = uuid.uuid4()
        func_b = uuid.uuid4()

        # Primer tope
        mock_repo.create.return_value = _limit(
            subscription_id=sub_id,
            functionality_id=func_a,
            functionality_key='orders.create',
        )
        result_a = use_case.execute(self._create_data(sub_id=sub_id, func_id=func_a))

        # Segundo tope (diferente funcionalidad, misma suscripción)
        mock_repo.create.return_value = _limit(
            subscription_id=sub_id,
            functionality_id=func_b,
            functionality_key='inventory.create',
        )
        result_b = use_case.execute(self._create_data(sub_id=sub_id, func_id=func_b))

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertNotEqual(result_a.functionality_id, result_b.functionality_id)
