"""Tests de la campanita del portal admin (dobles en memoria)."""

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from platform.features.communication.messaging.inbox.application.use_cases import (
    ArchiveAdminInboxUseCase,
    DeliverAdminInboxUseCase,
    GetAdminInboxUnreadCountUseCase,
    ListAdminInboxUseCase,
    MarkAdminInboxReadUseCase,
    MarkAllAdminInboxReadUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel, ReadStatus
from platform.features.communication.messaging.inbox.domain.schemas import AdminInboxPayload

pytestmark = pytest.mark.unit


def _payload(**kwargs):
    data = dict(
        title='Falló la tarea',
        body='Revisar Soporte.',
        level=NotificationLevel.WARNING,
        resource_type_code='automated_task',
        resource_route='/admin/support',
    )
    data.update(kwargs)
    return AdminInboxPayload(**data)


def test_list_delegates_to_repository():
    repo = MagicMock()
    repo.list_for_user.return_value = ([], 0)
    uid = uuid4()
    ListAdminInboxUseCase(repo).execute(uid, ReadStatus.UNREAD, limit=10, offset=0)
    repo.list_for_user.assert_called_once_with(uid, ReadStatus.UNREAD, 10, 0)


def test_unread_count_delegates():
    repo = MagicMock()
    repo.unread_count.return_value = 3
    uid = uuid4()
    assert GetAdminInboxUnreadCountUseCase(repo).execute(uid) == 3
    repo.unread_count.assert_called_once_with(uid)


def test_mark_one_passes_recipient_id():
    repo = MagicMock()
    repo.mark_read.return_value = 1
    uid, rid = uuid4(), uuid4()
    MarkAdminInboxReadUseCase(repo).execute(uid, rid)
    repo.mark_read.assert_called_once_with(uid, rid)


def test_mark_all_passes_none_recipient():
    repo = MagicMock()
    repo.mark_read.return_value = 4
    uid = uuid4()
    MarkAllAdminInboxReadUseCase(repo).execute(uid)
    repo.mark_read.assert_called_once_with(uid, None)


def test_archive_delegates():
    repo = MagicMock()
    repo.archive.return_value = 1
    uid, rid = uuid4(), uuid4()
    ArchiveAdminInboxUseCase(repo).execute(uid, rid)
    repo.archive.assert_called_once_with(uid, rid)


@patch(
    'platform.features.communication.messaging.inbox.application.use_cases.transaction.atomic',
    nullcontext,
)
def test_deliver_persists_and_pushes_to_each_user():
    repo = MagicMock()
    publisher = MagicMock()
    notification_id = uuid4()
    repo.create_notification.return_value = notification_id
    repo.add_recipients.return_value = 2
    u1, u2 = uuid4(), uuid4()

    count = DeliverAdminInboxUseCase(repo, publisher).execute(_payload(), [u1, u2, u1])

    assert count == 2
    repo.create_notification.assert_called_once()
    repo.add_recipients.assert_called_once_with(notification_id, [u1, u2])
    assert publisher.to_user.call_count == 2
    schemas = [c.args[0] for c in publisher.to_user.call_args_list]
    users = [c.args[1] for c in publisher.to_user.call_args_list]
    assert schemas == ['public', 'public']
    assert users == [u1, u2]
    assert publisher.to_user.call_args_list[0].args[2].type == 'notification.new'


def test_deliver_skips_when_no_recipients():
    repo = MagicMock()
    publisher = MagicMock()
    count = DeliverAdminInboxUseCase(repo, publisher).execute(_payload(), [])
    assert count == 0
    repo.create_notification.assert_not_called()
    publisher.to_user.assert_not_called()


@patch(
    'platform.features.communication.messaging.inbox.application.use_cases.transaction.atomic',
    nullcontext,
)
def test_deliver_swallows_publisher_errors():
    repo = MagicMock()
    publisher = MagicMock()
    repo.create_notification.return_value = uuid4()
    repo.add_recipients.return_value = 1
    publisher.to_user.side_effect = RuntimeError('ws down')

    count = DeliverAdminInboxUseCase(repo, publisher).execute(_payload(), [uuid4()])
    assert count == 1


@patch(
    'platform.features.communication.messaging.inbox.application.use_cases.transaction.atomic',
    nullcontext,
)
def test_deliver_persists_before_realtime_push():
    """Notification + recipients commit even if realtime push fails later."""
    repo = MagicMock()
    publisher = MagicMock()
    notification_id = uuid4()
    repo.create_notification.return_value = notification_id
    repo.add_recipients.return_value = 1
    publisher.to_user.side_effect = RuntimeError('ws down')
    uid = uuid4()

    count = DeliverAdminInboxUseCase(repo, publisher).execute(_payload(), [uid])

    assert count == 1
    assert repo.create_notification.called
    assert repo.add_recipients.called
    publisher.to_user.assert_called_once()
