"""Tests for ReconcileCompanyQuotasUseCase."""
import uuid
from unittest import TestCase
from unittest.mock import patch

from platform.features.billing.quota.quota_enforcement.application.use_cases import (
    ReconcileCompanyQuotasUseCase,
)


class TestReconcileCompanyQuotasUseCase(TestCase):
    @patch(
        'platform.features.billing.quota.quota_enforcement.application.use_cases'
        '.reconcile_company_quotas',
    )
    @patch(
        'platform.features.billing.quota.quota_enforcement.application.use_cases'
        '.load_subscription_limit_map',
    )
    def test_loads_limits_and_returns_schema(self, mock_load, mock_reconcile):
        company_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        limits = {'security.users.create': {'max': 5, 'type': 'lifetime'}}
        mock_load.return_value = limits

        from core.access.reconcile import CompanyQuotaReconcileResult

        mock_reconcile.return_value = CompanyQuotaReconcileResult(
            company_id=str(company_id),
            subscription_id=str(sub_id),
            features=[],
        )

        result = ReconcileCompanyQuotasUseCase().execute(company_id, sub_id)

        mock_load.assert_called_once_with(sub_id)
        mock_reconcile.assert_called_once_with(company_id, sub_id, limits=limits)
        self.assertEqual(result.company_id, str(company_id))
        self.assertEqual(result.subscription_id, str(sub_id))
