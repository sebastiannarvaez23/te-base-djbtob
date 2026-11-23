"""Wire support-session use cases with default adapters."""

from platform.features.support.sessions.session.application.use_cases import (
    AcceptSupportSessionUseCase,
    CancelSupportSessionUseCase,
    CloseSupportSessionUseCase,
    CreateSupportSessionUseCase,
    ExpireStaleSupportSessionsUseCase,
    GetActiveAgentSessionUseCase,
    GetActiveClientSessionUseCase,
    GetSupportSessionUseCase,
    GetSupportSettingsUseCase,
    ListSupportEventsUseCase,
    ListSupportMessagesUseCase,
    ListSupportSessionsUseCase,
    MarkAgentReadUseCase,
    MarkClientReadUseCase,
    RateSupportSessionUseCase,
    SendAgentMessageUseCase,
    SendClientMessageUseCase,
    UpdateSupportSettingsUseCase,
)
from platform.features.support.sessions.session.infrastructure.notifier import (
    AdminInboxSupportSessionNotifier,
)
from platform.features.support.sessions.session.infrastructure.realtime import (
    ChannelsSupportSessionRealtime,
)
from platform.features.support.sessions.session.infrastructure.repositories import (
    DjangoSupportSessionRepository,
    DjangoSupportSettingsRepository,
)


def _repo():
    return DjangoSupportSessionRepository()


def _notifier():
    return AdminInboxSupportSessionNotifier()


def _realtime():
    return ChannelsSupportSessionRealtime()


def build_create():
    return CreateSupportSessionUseCase(_repo(), _notifier(), _realtime())


def build_get_active_client():
    return GetActiveClientSessionUseCase(_repo())


def build_get_active_agent():
    return GetActiveAgentSessionUseCase(_repo())


def build_get():
    return GetSupportSessionUseCase(_repo())


def build_list():
    return ListSupportSessionsUseCase(_repo())


def build_accept():
    return AcceptSupportSessionUseCase(_repo(), _notifier(), _realtime())


def build_send_client():
    return SendClientMessageUseCase(_repo(), _realtime())


def build_send_agent():
    return SendAgentMessageUseCase(_repo(), _realtime())


def build_mark_client_read():
    return MarkClientReadUseCase(_repo(), _realtime())


def build_mark_agent_read():
    return MarkAgentReadUseCase(_repo(), _realtime())


def build_cancel():
    return CancelSupportSessionUseCase(_repo(), _realtime())


def build_close():
    return CloseSupportSessionUseCase(_repo(), _realtime())


def build_rate():
    return RateSupportSessionUseCase(_repo(), _realtime())


def build_list_messages():
    return ListSupportMessagesUseCase(_repo())


def build_list_events():
    return ListSupportEventsUseCase(_repo())


def _settings_repo():
    return DjangoSupportSettingsRepository()


def build_get_settings():
    return GetSupportSettingsUseCase(_settings_repo())


def build_update_settings():
    return UpdateSupportSettingsUseCase(_settings_repo())


def build_expire_stale():
    return ExpireStaleSupportSessionsUseCase(
        _repo(),
        _settings_repo(),
        _realtime(),
    )
