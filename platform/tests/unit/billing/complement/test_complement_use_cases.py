"""Unit tests for complement licenses and commercial offering rules."""
import uuid
from contextlib import nullcontext
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from core.query.core import PaginatedQuery, PaginatedResult
from core.validators import ValidationCode
from platform.features.billing.complement.entitlement.application.use_cases import (
    GrantCompanyComplementUseCase,
    ListCompanyComplementsUseCase,
    RevokeCompanyComplementUseCase,
)
from platform.features.billing.complement.entitlement.domain.schemas import (
    CompanyComplementSchema,
    ComplementFunctionalitySchema,
    GrantComplementSchema,
    RevokeComplementSchema,
)
from platform.features.billing.complement.entitlement.presentation.bodies import (
    GrantComplementBody,
    RevokeComplementBody,
)
from platform.features.billing.subscription.subscription_functionality.application.use_cases import (
    UpdateSubscriptionFunctionalitiesUseCase,
)
from platform.features.billing.subscription.subscription_functionality.domain.schemas import (
    UpdateSubscriptionFunctionalitiesSchema,
)
from platform.features.security.access.functionalities.application.use_cases import (
    CreateFunctionalityUseCase,
    UpdateFunctionalityUseCase,
)
from platform.features.security.access.functionalities.domain.schemas import (
    CreateFunctionalitySchema,
    FunctionalitySchema,
    UpdateFunctionalitySchema,
)


def _license(**overrides) -> CompanyComplementSchema:
    now = datetime.now()
    defaults = dict(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        functionality_id=uuid.uuid4(),
        functionality_key='connectors.sap',
        functionality_label='Conector SAP',
        module_code='connectors',
        billing_mode='one_time',
        status='active',
        source='admin_grant',
        starts_at=now,
        ends_at=None,
        notes='',
        auto_renew=False,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return CompanyComplementSchema(**defaults)


def _functionality(**overrides) -> FunctionalitySchema:
    now = datetime.now()
    defaults = dict(
        id=uuid.uuid4(),
        module='connectors',
        key='connectors.sap',
        label='Conector SAP',
        category='features',
        offering='plan',
        billing_mode='included',
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return FunctionalitySchema(**defaults)


class TestGrantCompanyComplementUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.use_case = GrantCompanyComplementUseCase(self.repo)
        self.company_id = uuid.uuid4()
        self.functionality_id = uuid.uuid4()
        self.data = GrantComplementSchema(
            company_id=self.company_id,
            functionality_id=self.functionality_id,
            notes='Contrato marco',
        )

    def test_activates_complement_and_invalidates_company_cache(self):
        self.repo.company_exists.return_value = True
        self.repo.get_grantable.return_value = ComplementFunctionalitySchema(
            id=self.functionality_id, key='connectors.sap', billing_mode='renewal',
        )
        created = _license(company_id=self.company_id, functionality_id=self.functionality_id)
        self.repo.create_active.return_value = created

        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ), patch(
            'platform.features.billing.complement.entitlement.application.use_cases.SubscriptionCache',
        ) as cache:
            result = self.use_case.execute(self.data)

        self.assertEqual(result.id, created.id)
        self.repo.create_active.assert_called_once_with(self.data, 'renewal')
        cache.invalidate.assert_called_once_with(str(self.company_id))

    def test_activates_module_complement(self):
        module_id = uuid.uuid4()
        data = GrantComplementSchema(company_id=self.company_id, module_id=module_id)
        self.repo.company_exists.return_value = True
        self.repo.get_grantable_module.return_value = ComplementFunctionalitySchema(
            id=module_id, key='connectors', billing_mode='one_time',
        )
        created = _license(company_id=self.company_id, functionality_id=None, module_id=module_id)
        self.repo.create_active.return_value = created

        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ), patch(
            'platform.features.billing.complement.entitlement.application.use_cases.SubscriptionCache',
        ):
            result = self.use_case.execute(data)

        self.assertEqual(result.id, created.id)
        self.repo.get_grantable.assert_not_called()
        self.repo.create_active.assert_called_once_with(data, 'one_time')

    def test_missing_company(self):
        self.repo.company_exists.return_value = False
        with self.assertRaises(NotFoundException) as caught:
            self.use_case.execute(self.data)
        self.assertEqual(caught.exception.code, AppErrorCode.COMPANY_NOT_FOUND)
        self.repo.create_active.assert_not_called()

    def test_functionality_is_not_an_active_complement(self):
        self.repo.company_exists.return_value = True
        self.repo.get_grantable.return_value = None
        with self.assertRaises(ValidationAppException) as caught:
            self.use_case.execute(self.data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_NOT_AVAILABLE)

    def test_concurrent_grant_is_rejected(self):
        self.repo.company_exists.return_value = True
        self.repo.get_grantable.return_value = ComplementFunctionalitySchema(
            id=self.functionality_id, key='connectors.sap', billing_mode='one_time',
        )
        self.repo.create_active.side_effect = IntegrityError()
        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ), patch(
            'platform.features.billing.complement.entitlement.application.use_cases.SubscriptionCache',
        ) as cache:
            with self.assertRaises(ConflictException) as caught:
                self.use_case.execute(self.data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_ALREADY_ACTIVE)
        cache.invalidate.assert_not_called()

    def test_unrelated_integrity_error_is_not_masked(self):
        self.repo.company_exists.return_value = True
        self.repo.get_grantable.return_value = ComplementFunctionalitySchema(
            id=self.functionality_id, key='connectors.sap', billing_mode='one_time',
        )
        cause = IntegrityError('fk')
        cause.diag = MagicMock(constraint_name='billing_company_complements_company_id_fkey')
        raised = IntegrityError('wrapped')
        raised.__cause__ = cause
        self.repo.create_active.side_effect = raised
        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ):
            with self.assertRaises(IntegrityError):
                self.use_case.execute(self.data)


class TestRevokeCompanyComplementUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.use_case = RevokeCompanyComplementUseCase(self.repo)
        self.company_id = uuid.uuid4()
        self.entitlement_id = uuid.uuid4()
        self.data = RevokeComplementSchema(
            company_id=self.company_id,
            entitlement_id=self.entitlement_id,
            notes='Fin de contrato',
        )

    def test_revokes_active_license(self):
        self.repo.company_exists.return_value = True
        current = _license(id=self.entitlement_id, company_id=self.company_id, status='active')
        revoked = _license(id=self.entitlement_id, company_id=self.company_id, status='revoked')
        self.repo.get_for_company.return_value = current
        self.repo.mark_revoked.return_value = revoked
        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ), patch(
            'platform.features.billing.complement.entitlement.application.use_cases.SubscriptionCache',
        ) as cache:
            result = self.use_case.execute(self.data)
        self.assertEqual(result.status, 'revoked')
        self.repo.get_for_company.assert_called_once_with(
            self.company_id, self.entitlement_id, lock=True,
        )
        cache.invalidate.assert_called_once_with(str(self.company_id))

    def test_missing_license(self):
        self.repo.company_exists.return_value = True
        self.repo.get_for_company.return_value = None
        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ):
            with self.assertRaises(NotFoundException) as caught:
                self.use_case.execute(self.data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_NOT_FOUND)

    def test_already_revoked(self):
        self.repo.company_exists.return_value = True
        self.repo.get_for_company.return_value = _license(status='revoked')
        with patch(
            'platform.features.billing.complement.entitlement.application.use_cases.transaction.atomic',
            return_value=nullcontext(),
        ):
            with self.assertRaises(ConflictException) as caught:
                self.use_case.execute(self.data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_NOT_ACTIVE)
        self.repo.mark_revoked.assert_not_called()


class TestListCompanyComplementsUseCase(TestCase):

    def test_unknown_company(self):
        repo = MagicMock()
        repo.company_exists.return_value = False
        with self.assertRaises(NotFoundException):
            ListCompanyComplementsUseCase(repo).execute(uuid.uuid4(), MagicMock(spec=PaginatedQuery))


class TestOfferingRules(TestCase):

    def test_create_rejects_complement_included_in_plan(self):
        repo = MagicMock()
        data = CreateFunctionalitySchema(
            module='connectors',
            key='connectors.sap',
            label='Conector SAP',
            offering='complement',
            billing_mode='included',
        )
        with self.assertRaises(ValidationAppException) as caught:
            CreateFunctionalityUseCase(repo).execute(data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_OFFERING_MISMATCH)
        repo.create.assert_not_called()

    def test_create_accepts_one_time_complement(self):
        repo = MagicMock()
        data = CreateFunctionalitySchema(
            module='connectors',
            key='connectors.shopify',
            label='Conector Shopify',
            offering='complement',
            billing_mode='one_time',
        )
        repo.create.return_value = _functionality(offering='complement', billing_mode='one_time')
        with patch(
            'platform.features.security.access.functionalities.application.use_cases.Functionality',
        ) as model:
            model.objects.filter.return_value.exists.return_value = False
            CreateFunctionalityUseCase(repo).execute(data)
        repo.create.assert_called_once_with(data)

    @patch('platform.features.billing.complement.entitlement.models.CompanyComplement')
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality')
    def test_offering_change_locked_when_plan_or_license_exists(self, plan_link, licenses):
        plan_link.objects.filter.return_value.exists.return_value = True
        licenses.objects.filter.return_value.exists.return_value = False
        repo = MagicMock()
        current = _functionality(offering='plan', billing_mode='included')
        repo.get_by_id.return_value = current
        data = UpdateFunctionalitySchema(offering='complement', billing_mode='renewal')
        with patch(
            'platform.features.security.access.functionalities.application.use_cases.Functionality',
        ):
            with self.assertRaises(ConflictException) as caught:
                UpdateFunctionalityUseCase(repo).execute(current.id, data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_OFFERING_LOCKED)
        repo.update.assert_not_called()

    def test_renewal_requires_neurana_service(self):
        repo = MagicMock()
        data = CreateFunctionalitySchema(
            module='connectors',
            key='connectors.sap',
            label='Conector SAP',
            offering='complement',
            billing_mode='renewal',
        )
        with self.assertRaises(ValidationAppException) as caught:
            CreateFunctionalityUseCase(repo).execute(data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_SERVICE_REQUIRED)
        repo.create.assert_not_called()

    @patch('platform.features.billing.subscription.subscription.infrastructure.neurana_catalog.require_active_service')
    def test_renewal_accepts_active_neurana_service(self, require_service):
        repo = MagicMock()
        service_id = uuid.uuid4()
        data = CreateFunctionalitySchema(
            module='connectors',
            key='connectors.sap',
            label='Conector SAP',
            offering='complement',
            billing_mode='renewal',
            catalog_service_id=service_id,
        )
        repo.create.return_value = _functionality(
            offering='complement', billing_mode='renewal', catalog_service_id=service_id,
        )
        with patch(
            'platform.features.security.access.functionalities.application.use_cases.Functionality',
        ) as model:
            model.objects.filter.return_value.exists.return_value = False
            CreateFunctionalityUseCase(repo).execute(data)
        require_service.assert_called_once_with(service_id)
        repo.create.assert_called_once_with(data)

    def test_module_renewal_requires_neurana_service(self):
        from platform.features.security.access.modules.application.use_cases import CreateModuleUseCase
        from platform.features.security.access.modules.domain.schemas import CreateModuleSchema

        data = CreateModuleSchema(
            code='connectors',
            name='Conectores',
            icon='bx-plug',
            route='/connectors',
            section_id=uuid.uuid4(),
            offering='complement',
            billing_mode='renewal',
        )
        with self.assertRaises(ValidationAppException) as caught:
            CreateModuleUseCase(MagicMock()).execute(data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_SERVICE_REQUIRED)


class TestPlanRejectsComplements(TestCase):

    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_replace_rejects_complement_keys(self, functionality):
        functionality.Offering.COMPLEMENT = 'complement'
        functionality.objects.filter.return_value.exists.return_value = True
        repo = MagicMock()
        data = UpdateSubscriptionFunctionalitiesSchema(functionality_keys=['connectors.sap'])
        with self.assertRaises(ConflictException) as caught:
            UpdateSubscriptionFunctionalitiesUseCase(repo).execute(uuid.uuid4(), data)
        self.assertEqual(caught.exception.code, AppErrorCode.CMP_NOT_ON_PLAN)
        repo.update_functionalities.assert_not_called()


class TestComplementBodies(TestCase):

    def test_unknown_field_rejected(self):
        body = GrantComplementBody({
            'functionality_id': str(uuid.uuid4()),
            'price': '10',
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.UNKNOWN_FIELD)

    def test_functionality_id_must_be_uuid(self):
        body = GrantComplementBody({'functionality_id': 'sap'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'functionality_id')

    def test_revoke_notes_optional(self):
        body = RevokeComplementBody({})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['notes'], '')

    def test_grant_requires_exactly_one_target(self):
        missing = GrantComplementBody({})
        ok, errors = missing.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'functionality_id')

        both = GrantComplementBody({
            'functionality_id': str(uuid.uuid4()),
            'module_id': str(uuid.uuid4()),
        })
        ok, errors = both.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'functionality_id')

        module_only = GrantComplementBody({'module_id': str(uuid.uuid4())})
        ok, errors = module_only.validate()
        self.assertTrue(ok, errors)


class TestListResultShape(TestCase):

    def test_paginated_placeholder(self):
        result = PaginatedResult(items=[], total=0, page=0, page_size=20, total_pages=0)
        self.assertEqual(result.total, 0)
