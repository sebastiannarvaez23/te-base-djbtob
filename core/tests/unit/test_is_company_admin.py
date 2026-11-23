from types import SimpleNamespace

import pytest

from core.errors import AppErrorCode, PermissionException
from core.permissions import IsCompanyAdmin

pytestmark = pytest.mark.unit


def _request(role='Administrator', company_id='c-1', authenticated=True):
    user = SimpleNamespace(is_authenticated=authenticated, company_id=company_id, rol=SimpleNamespace(name=role))
    return SimpleNamespace(user=user)


def test_company_administrator_is_allowed():
    assert IsCompanyAdmin().has_permission(_request(), None) is True


def test_other_roles_are_denied_with_perm_001():
    with pytest.raises(PermissionException) as caught:
        IsCompanyAdmin().has_permission(_request(role='Operator'), None)
    assert caught.value.code == AppErrorCode.PERM_INSUFFICIENT


@pytest.mark.parametrize('request_', [_request(company_id=None), _request(authenticated=False)])
def test_non_members_are_rejected(request_):
    assert not IsCompanyAdmin().has_permission(request_, None)
