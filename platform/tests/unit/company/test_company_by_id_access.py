"""Company-by-id access helper and UpdateCompanyBody NIT rules."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, NotFoundException
from platform.core.authentication import AdminTokenAuthentication
from platform.features.company.tenant.company.presentation.api import _assert_company_access
from platform.features.company.tenant.company.presentation.bodies import UpdateCompanyBody

pytestmark = pytest.mark.unit


def test_admin_authenticator_skips_tenant_match():
    request = SimpleNamespace(
        successful_authenticator=AdminTokenAuthentication(),
        user=SimpleNamespace(company_id=uuid4()),
    )
    _assert_company_access(request, uuid4())


def test_tenant_mismatch_is_not_found():
    request = SimpleNamespace(
        successful_authenticator=None,
        user=SimpleNamespace(company_id=uuid4()),
    )
    with pytest.raises(NotFoundException) as exc:
        _assert_company_access(request, uuid4())
    assert exc.value.code == AppErrorCode.COMPANY_NOT_FOUND


def test_tenant_match_allows_access():
    company_id = uuid4()
    request = SimpleNamespace(
        successful_authenticator=object(),
        user=SimpleNamespace(company_id=company_id),
    )
    _assert_company_access(request, company_id)


def test_update_company_body_rejects_short_nit():
    data, err = UpdateCompanyBody({'nit': '123'}).parse()
    assert data is None
    assert err is not None


def test_update_company_body_strips_nit_dots():
    data, err = UpdateCompanyBody({'nit': '900.123.456'}).parse()
    assert err is None
    assert data['nit'] == '900123456'
