"""Tests del fan-out: mapeo scope→kind y enrutamiento por schema."""

import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from client.features.communication.messaging.inbox.domain.enums import NotificationKind
from client.features.communication.messaging.inbox.infrastructure.fanout import FanoutDispatcher
from client.features.communication.messaging.inbox.tasks.fanout import _payload_from_outbox
from platform.features.communication.messaging.inbox.domain.enums import AudienceScope
from platform.features.communication.messaging.inbox.domain.schemas import RecipientGroup

pytestmark = pytest.mark.unit


def _outbox(scope):
    return SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),
        admin_label='Admin',
        scope=scope,
        title='Aviso',
        body='cuerpo',
        level='INFO',
    )


@pytest.mark.parametrize('scope,expected', [
    (AudienceScope.SINGLE_USER, NotificationKind.ADMIN_DIRECT),
    (AudienceScope.COMPANY_USERS, NotificationKind.ADMIN_COMPANY),
    (AudienceScope.ALL_TENANTS, NotificationKind.ADMIN_BROADCAST),
])
def test_payload_kind_mapping(scope, expected):
    payload = _payload_from_outbox(_outbox(scope))
    assert payload.kind == expected
    assert payload.origin_id is not None


def test_dispatch_enters_each_schema_and_aggregates_count():
    manager = MagicMock()
    manager.deliver.side_effect = lambda schema, payload, users: len(users)

    groups = [
        RecipientGroup(schema_name='acme', user_ids=[uuid.uuid4(), uuid.uuid4()]),
        RecipientGroup(schema_name='globex', user_ids=[uuid.uuid4()]),
    ]
    payload = _payload_from_outbox(_outbox(AudienceScope.ALL_TENANTS))

    with patch(
        'client.features.communication.messaging.inbox.infrastructure.fanout.schema_context',
        lambda schema: nullcontext(),
    ):
        total = FanoutDispatcher(manager).dispatch(payload, groups)

    assert total == 3
    assert manager.deliver.call_count == 2
    # Cada grupo se entrega con su propio schema.
    called_schemas = {call.args[0] for call in manager.deliver.call_args_list}
    assert called_schemas == {'acme', 'globex'}
