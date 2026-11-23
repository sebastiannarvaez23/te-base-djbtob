"""El contexto de log conserva el UUID del usuario autenticado."""
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from client.features.logging.facade.context import LogContextBuilder
from core.audit import INTEGRATION_ACTOR_KEY, integration_actor, warehouse_event_log
from core.auth.integration.principal import IntegrationPrincipal
from core.ids import uuid7

pytestmark = pytest.mark.unit


def test_from_request_keeps_the_authenticated_user_uuid():
    user_id = uuid7()
    tenant_id = uuid7()
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, pk=user_id),
        tenant=SimpleNamespace(id=tenant_id),
        request_id='req-share',
        META={'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'test'},
    )

    context = LogContextBuilder.from_request(request)

    assert context.user_id == user_id
    assert context.warehouse_id == tenant_id
    assert isinstance(context.user_id, uuid.UUID)


def test_from_request_ignores_a_legacy_integer_user_id():
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, pk=7),
        tenant=None,
        request_id='req-legacy',
        META={'REMOTE_ADDR': '127.0.0.1'},
    )

    context = LogContextBuilder.from_request(request)

    assert context.user_id is None
    assert context.warehouse_id is None


def _integration_request():
    principal = IntegrationPrincipal(
        app_id=str(uuid7()), client_id='wa_erp', schema_name='tenant_a', scopes=[], name='ERP',
    )
    return SimpleNamespace(
        user=principal, tenant=None, request_id='req-api', META={'REMOTE_ADDR': '10.0.0.1'},
    ), principal


def test_an_integration_app_is_never_logged_as_a_user():
    request, _principal = _integration_request()
    assert LogContextBuilder.from_request(request).user_id is None


def test_warehouse_events_name_the_integration_app():
    request, principal = _integration_request()
    with patch('core.audit.transaction.atomic', return_value=nullcontext()), \
            patch('client.features.logging.facade.factory.LogManagerFactory.create') as create:
        warehouse_event_log(request, 'warehouse.updated', payload={'code': 'BOG'})
    ctx, event = create.return_value.warehouse_event.call_args.args
    assert ctx.user_id is None
    assert event.payload == {
        'code': 'BOG',
        INTEGRATION_ACTOR_KEY: {'id': principal.app_id, 'client_id': 'wa_erp', 'name': 'ERP'},
    }


def test_human_requests_carry_no_integration_actor():
    request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, pk=uuid7()))
    assert integration_actor(request) is None
