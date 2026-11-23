"""Tests de los casos de uso de lectura de la campanita (aislamiento por usuario)."""

import uuid
from unittest.mock import MagicMock

import pytest

from client.features.communication.messaging.inbox.application.use_cases import (
    ArchiveNotificationUseCase,
    GetUnreadCountUseCase,
    ListInboxUseCase,
    MarkAllReadUseCase,
    MarkNotificationReadUseCase,
)
from client.features.communication.messaging.inbox.domain.enums import ReadStatus

pytestmark = pytest.mark.unit


def test_list_delegates_to_repository():
    repo = MagicMock()
    repo.list_for_user.return_value = ([], 0)
    uid = uuid.uuid4()
    ListInboxUseCase(repo).execute(uid, ReadStatus.UNREAD, limit=10, offset=0)
    repo.list_for_user.assert_called_once_with(uid, ReadStatus.UNREAD, 10, 0)


def test_unread_count_delegates():
    repo = MagicMock()
    repo.unread_count.return_value = 5
    uid = uuid.uuid4()
    assert GetUnreadCountUseCase(repo).execute(uid) == 5
    repo.unread_count.assert_called_once_with(uid)


def test_mark_one_passes_recipient_id():
    repo = MagicMock()
    repo.mark_read.return_value = 1
    uid, rid = uuid.uuid4(), uuid.uuid4()
    MarkNotificationReadUseCase(repo).execute(uid, rid)
    repo.mark_read.assert_called_once_with(uid, rid)


def test_mark_all_passes_none_recipient():
    repo = MagicMock()
    repo.mark_read.return_value = 4
    uid = uuid.uuid4()
    MarkAllReadUseCase(repo).execute(uid)
    repo.mark_read.assert_called_once_with(uid, None)


def test_archive_delegates():
    repo = MagicMock()
    repo.archive.return_value = 1
    uid, rid = uuid.uuid4(), uuid.uuid4()
    ArchiveNotificationUseCase(repo).execute(uid, rid)
    repo.archive.assert_called_once_with(uid, rid)
