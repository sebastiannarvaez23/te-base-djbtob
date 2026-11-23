"""Tests del aviso de campanita al fallar una tarea automatizada."""

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel
from platform.features.support.ops.task_monitor.infrastructure.failure_notifier import (
    AUTOMATED_TASK_ADMIN_FEATURE_KEY,
    AdminInboxTaskFailureNotifier,
)

pytestmark = pytest.mark.unit

_TASK = 'onboarding.purge_expired'


def test_notify_failed_skips_when_no_audience():
    lookup = MagicMock()
    lookup.user_ids_for_feature.return_value = []
    deliver = MagicMock()

    count = AdminInboxTaskFailureNotifier(lookup=lookup, deliver=deliver).notify_failed(
        task_key=_TASK,
        run_id=uuid4(),
        error_summary='boom',
    )

    assert count == 0
    lookup.user_ids_for_feature.assert_called_once_with(AUTOMATED_TASK_ADMIN_FEATURE_KEY)
    deliver.execute.assert_not_called()


def test_notify_failed_delivers_warning_to_feature_audience():
    lookup = MagicMock()
    users = [uuid4(), uuid4()]
    lookup.user_ids_for_feature.return_value = users
    deliver = MagicMock()
    deliver.execute.return_value = 2
    run_id = uuid4()

    count = AdminInboxTaskFailureNotifier(lookup=lookup, deliver=deliver).notify_failed(
        task_key=_TASK,
        run_id=run_id,
        error_summary='Lock timeout',
    )

    assert count == 2
    payload = deliver.execute.call_args.args[0]
    recipients = deliver.execute.call_args.args[1]
    assert recipients == users
    assert payload.level is NotificationLevel.WARNING
    assert payload.resource_type_code == 'automated_task'
    assert payload.resource_id == run_id
    assert payload.resource_route == '/admin/support'
    assert 'Purge' in payload.title
    assert 'Lock timeout' in payload.body
    assert 'Automated tasks' in payload.body


def test_notify_failed_uses_fallback_copy_without_error_summary():
    lookup = MagicMock()
    lookup.user_ids_for_feature.return_value = [uuid4()]
    deliver = MagicMock()
    deliver.execute.return_value = 1

    AdminInboxTaskFailureNotifier(lookup=lookup, deliver=deliver).notify_failed(
        task_key='unknown.task',
        run_id=uuid4(),
        error_summary='  ',
    )

    payload = deliver.execute.call_args.args[0]
    assert payload.title.endswith('«unknown.task»') or 'unknown.task' in payload.title
    assert 'The task ended with an error.' in payload.body


def test_audience_lookup_empty_key_short_circuits():
    from platform.features.communication.messaging.inbox.infrastructure.repositories import (
        DjangoAdminFeatureAudienceLookup,
    )

    assert DjangoAdminFeatureAudienceLookup().user_ids_for_feature('') == []
    assert DjangoAdminFeatureAudienceLookup().user_ids_for_feature('   ') == []


def test_audience_lookup_includes_superusers_and_feature_roles():
    from unittest.mock import patch

    from platform.features.communication.messaging.inbox.infrastructure.repositories import (
        DjangoAdminFeatureAudienceLookup,
    )

    uid = uuid4()
    with patch('platform.features.security.identity.users.models.AdminUser') as MockUser:
        qs = MockUser.objects.filter.return_value.filter.return_value
        qs.values_list.return_value.distinct.return_value = [uid]
        result = DjangoAdminFeatureAudienceLookup().user_ids_for_feature(
            'support.automate-task',
        )

    assert result == [uid]
    MockUser.objects.filter.assert_called_once_with(is_active=True)
    second = MockUser.objects.filter.return_value.filter
    second.assert_called_once()
    q_obj = second.call_args.args[0]
    combined = str(q_obj)
    assert 'is_superuser' in combined
    assert 'support.automate-task' in combined
