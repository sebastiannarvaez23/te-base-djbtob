"""Vistas de entity_grants con use cases sobre fakes (sin DB)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from client.features.security.access.entity_grants.application.use_cases import (
    GetGrantSetUseCase,
    ReplaceGrantSetUseCase,
)
from client.features.security.access.entity_grants.presentation.api import (
    EntityGrantSetView,
    UserGrantSetView,
)
from client.tests.unit.security.access.grant_fakes import (
    ADMIN,
    COMPANY,
    NORTH,
    SOUTH,
    USER,
    FakeCatalog,
    FakeDirectory,
    FakeRepository,
    SpyInvalidator,
)

pytestmark = pytest.mark.unit

API = 'client.features.security.access.entity_grants.presentation.api'


@pytest.fixture
def env():
    repo, spy = FakeRepository(), SpyInvalidator()
    with patch(f'{API}.deps.get_grant_set', lambda _type: GetGrantSetUseCase(repo, FakeDirectory(), FakeCatalog())), \
            patch(f'{API}.deps.replace_grant_set',
                  lambda _type: ReplaceGrantSetUseCase(repo, FakeDirectory(), FakeCatalog(), spy)), \
            patch(f'{API}.audit_log') as audit:
        yield SimpleNamespace(repo=repo, spy=spy, audit=audit)


def _call(view, method, key_id, data=None, role='Administrator'):
    factory = APIRequestFactory()
    path = f'/access/entity-grants/x/{key_id}/'
    if method == 'get':
        request = factory.get(path, data or {})
    else:
        request = factory.put(path, data, format='json')
    user = SimpleNamespace(
        id=ADMIN, pk=ADMIN, is_authenticated=True, company_id=COMPANY, rol=SimpleNamespace(name=role),
    )
    force_authenticate(request, user=user)
    response = view.as_view()(request, key_id=key_id)
    response.render()
    return response


def test_put_rejects_unregistered_entity_type(env):
    response = _call(UserGrantSetView, 'put', USER, {'entity_type': 'warehouse', 'ids': [str(NORTH)]})

    assert response.status_code == 400
    assert env.repo.rows == set()
    env.audit.assert_not_called()


def test_put_without_changes_does_not_audit(env):
    _call(UserGrantSetView, 'put', USER, {'entity_type': 'warehouse', 'ids': [str(NORTH)]})
    env.audit.reset_mock()

    _call(UserGrantSetView, 'put', USER, {'entity_type': 'warehouse', 'ids': [str(NORTH)]})

    env.audit.assert_not_called()


def test_get_rejects_unregistered_entity_type(env):
    response = _call(EntityGrantSetView, 'get', SOUTH, {'entity_type': 'warehouse'})

    assert response.status_code == 400
    assert env.repo.rows == set()


def test_operator_is_not_blocked_by_a_product_scope(env):
    with patch(
        'client.features.security.access.entity_grants.presentation.api.HasSubscriptionAccess.has_permission',
        return_value=True,
    ):
        response = _call(
            EntityGrantSetView, 'get', SOUTH, {'entity_type': 'warehouse'}, role='Operator',
        )

    assert response.status_code == 400


def test_get_requires_entity_type(env):
    response = _call(UserGrantSetView, 'get', USER)
    assert response.status_code == 400


def test_put_rejects_invalid_body(env):
    response = _call(UserGrantSetView, 'put', USER, {'entity_type': 'warehouse', 'ids': ['nope']})
    assert response.status_code == 400
    assert env.repo.rows == set()


def test_non_admin_is_forbidden(env):
    response = _call(UserGrantSetView, 'get', USER, {'entity_type': 'warehouse'}, role='Operator')
    assert response.status_code == 403
    assert response.data['error']['code'] == 'PERM_001'
