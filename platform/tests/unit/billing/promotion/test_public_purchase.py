"""Unit tests for the public purchase billing-company adapter."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from platform.features.billing.commerce.promotion.infrastructure.adapters.billing_company import (
    DjangoBillingCompany,
)

pytestmark = pytest.mark.unit


@override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID='')
@patch('platform.features.company.tenant.company.models.Company.objects')
def test_resolve_billing_company_orders_by_created(mock_objects):
    company = MagicMock()
    company.id = uuid.uuid4()
    mock_objects.order_by.return_value.first.return_value = company

    result = DjangoBillingCompany().resolve_public_billing_company_id()

    mock_objects.order_by.assert_called_once_with('created')
    assert result == company.id


@override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
def test_resolve_billing_company_uses_setting_when_configured():
    result = DjangoBillingCompany().resolve_public_billing_company_id()
    assert result == uuid.UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
