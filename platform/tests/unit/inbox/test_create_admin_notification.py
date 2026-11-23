"""Tests del caso de uso de envío del administrador (escenario 2)."""

import uuid
from unittest.mock import MagicMock

import pytest

from core.errors.exceptions import ValidationAppException

from platform.features.communication.messaging.inbox.application.use_cases import (
    CreateAdminNotificationUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import AudienceScope
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminNotifyInput,
    Audience,
)

pytestmark = pytest.mark.unit


def _input(scope, **audience):
    return AdminNotifyInput(
        admin_id=uuid.uuid4(),
        admin_label='Admin Root',
        title='Mantenimiento programado',
        body='El sistema estará en mantenimiento.',
        audience=Audience(scope=scope, **audience),
    )


def test_broadcast_creates_outbox_and_triggers_fanout():
    outbox_repo = MagicMock()
    created = MagicMock()
    created.id = uuid.uuid4()
    outbox_repo.create.return_value = created
    trigger = MagicMock()

    use_case = CreateAdminNotificationUseCase(outbox_repo, trigger)
    result = use_case.execute(_input(AudienceScope.ALL_TENANTS))

    outbox_repo.create.assert_called_once()
    trigger.trigger.assert_called_once_with(created.id)
    assert result is created


def test_single_user_requires_target_user():
    use_case = CreateAdminNotificationUseCase(MagicMock(), MagicMock())
    with pytest.raises(ValidationAppException):
        use_case.execute(_input(AudienceScope.SINGLE_USER))


def test_company_scope_requires_target_company():
    use_case = CreateAdminNotificationUseCase(MagicMock(), MagicMock())
    with pytest.raises(ValidationAppException):
        use_case.execute(_input(AudienceScope.COMPANY_USERS))


def test_invalid_audience_does_not_create_or_trigger():
    outbox_repo, trigger = MagicMock(), MagicMock()
    use_case = CreateAdminNotificationUseCase(outbox_repo, trigger)
    with pytest.raises(ValidationAppException):
        use_case.execute(_input(AudienceScope.SINGLE_USER))
    outbox_repo.create.assert_not_called()
    trigger.trigger.assert_not_called()
