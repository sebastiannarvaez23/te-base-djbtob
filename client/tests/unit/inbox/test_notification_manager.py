"""Tests del facade NotificationManager (emisión: escenario 1 + entrega)."""

import uuid
from unittest.mock import MagicMock

import pytest

from core.errors.exceptions import ConflictException, NotFoundException

from client.features.communication.messaging.inbox.domain.context import NotificationContext
from client.features.communication.messaging.inbox.domain.enums import ActorKind, NotificationKind
from client.features.communication.messaging.inbox.domain.schemas import ShareInput
from client.features.communication.messaging.inbox.facade.manager import NotificationManager

pytestmark = pytest.mark.unit


def _context():
    return NotificationContext(actor_kind=ActorKind.USER, actor_label='Juan', actor_id=uuid.uuid4())


def _share_input(n=2):
    return ShareInput(
        resource_type_code='PICKING',
        resource_id=uuid.uuid4(),
        recipient_user_ids=[uuid.uuid4() for _ in range(n)],
        title='Te compartieron un picking',
    )


def _manager(repo, resource_repo, publisher):
    return NotificationManager(repo, resource_repo, publisher)


def test_share_creates_notification_recipients_and_publishes():
    repo = MagicMock()
    repo.create_notification.return_value = uuid.uuid4()
    repo.add_recipients.return_value = 2
    resource_repo = MagicMock()
    resource_repo.get_by_code.return_value = MagicMock(is_active=True)
    publisher = MagicMock()

    data = _share_input(n=2)
    count = _manager(repo, resource_repo, publisher).share(_context(), data, schema_name='acme')

    assert count == 2
    # El payload materializado debe ser un SHARE con el recurso.
    payload = repo.create_notification.call_args[0][0]
    assert payload.kind == NotificationKind.SHARE
    assert payload.resource_type_code == 'PICKING'
    repo.add_recipients.assert_called_once()
    # Publica en vivo a cada destinatario.
    assert publisher.to_user.call_count == 2


def test_share_raises_when_resource_type_missing():
    resource_repo = MagicMock()
    resource_repo.get_by_code.return_value = None
    with pytest.raises(NotFoundException):
        _manager(MagicMock(), resource_repo, MagicMock()).share(_context(), _share_input(), 'acme')


def test_share_raises_when_resource_type_inactive():
    resource_repo = MagicMock()
    resource_repo.get_by_code.return_value = MagicMock(is_active=False)
    with pytest.raises(ConflictException):
        _manager(MagicMock(), resource_repo, MagicMock()).share(_context(), _share_input(), 'acme')


def test_deliver_emits_without_resource_validation():
    repo = MagicMock()
    repo.create_notification.return_value = uuid.uuid4()
    repo.add_recipients.return_value = 3
    publisher = MagicMock()

    from client.features.communication.messaging.inbox.domain.schemas import NotificationPayload
    payload = NotificationPayload(
        kind=NotificationKind.ADMIN_BROADCAST,
        actor_kind=ActorKind.ADMIN,
        actor_label='Admin',
        title='Aviso',
    )
    users = [uuid.uuid4() for _ in range(3)]
    count = _manager(repo, MagicMock(), publisher).deliver('acme', payload, users)

    assert count == 3
    assert publisher.to_user.call_count == 3
