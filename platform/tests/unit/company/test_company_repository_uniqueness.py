"""Company repository maps NIT uniqueness IntegrityError."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.company.tenant.company.domain.schemas import (
    CreateCompanySchema,
    UpdateCompanySchema,
)
from platform.features.company.tenant.company.infrastructure.repositories import (
    DjangoCompanyRepository,
)

pytestmark = pytest.mark.unit

REPO = 'platform.features.company.tenant.company.infrastructure.repositories'


@patch(f'{REPO}.transaction.atomic')
@patch(f'{REPO}.Company.objects')
def test_create_maps_nit_unique_integrity_error(objects, atomic):
    atomic.return_value.__enter__.return_value = None
    atomic.return_value.__exit__.return_value = False
    objects.create.side_effect = IntegrityError(
        'duplicate key value violates unique constraint "uniq_company_nit_when_set"'
    )

    with pytest.raises(ConflictException) as exc:
        DjangoCompanyRepository().create(CreateCompanySchema(
            schema_name='acme',
            nit='900123456',
            name='Acme',
            address='Calle 1 # 2-3',
            geo_city_id=uuid4(),
            subscription_id=uuid4(),
        ))

    assert exc.value.code == AppErrorCode.COMPANY_DUPLICATE_NIT


@patch(f'{REPO}.transaction.atomic')
@patch(f'{REPO}.Company.objects')
def test_update_settings_maps_nit_unique_integrity_error(objects, atomic):
    atomic.return_value.__enter__.return_value = None
    atomic.return_value.__exit__.return_value = False
    company = MagicMock()
    company.nit = ''
    company.save.side_effect = IntegrityError(
        'duplicate key value violates unique constraint "uniq_company_nit_when_set"'
    )
    objects.select_related.return_value.get.return_value = company

    with pytest.raises(ConflictException) as exc:
        DjangoCompanyRepository().update_settings(
            uuid4(),
            UpdateCompanySchema(nit='900123456'),
        )

    assert exc.value.code == AppErrorCode.COMPANY_DUPLICATE_NIT
