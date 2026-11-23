"""Unit tests for live support session use cases."""
from __future__ import annotations

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest import TestCase
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException, ValidationAppException
from platform.features.support.sessions.session.application.use_cases import (
    AGENT_JOINED_MESSAGE,
    ASK_MOTIVE_MESSAGE,
    AcceptSupportSessionUseCase,
    CancelSupportSessionUseCase,
    CloseSupportSessionUseCase,
    CreateSupportSessionUseCase,
    ExpireStaleSupportSessionsUseCase,
    ListSupportMessagesUseCase,
    RateSupportSessionUseCase,
    SendAgentMessageUseCase,
    SendClientMessageUseCase,
    UpdateSupportSettingsUseCase,
)
from platform.features.support.sessions.session.domain import constants as c
from platform.features.support.sessions.session.domain.interfaces import (
    ISupportSessionNotifier,
    ISupportSessionRealtime,
    ISupportSessionRepository,
    ISupportSettingsRepository,
)
from platform.features.support.sessions.session.domain.schemas import (
    AcceptSupportSessionSchema,
    CreateSupportSessionSchema,
    RateSupportSessionSchema,
    SendSupportMessageSchema,
    SupportSessionEventView,
    SupportSessionMessageView,
    SupportSessionView,
    SupportSettingsSchema,
    UpdateSupportSettingsSchema,
    normalize_whatsapp_url,
)

pytestmark = pytest.mark.unit


def _now():
    return datetime.now(timezone.utc)


def _session(**overrides) -> SupportSessionView:
    base = dict(
        id=uuid4(),
        company_id='c1',
        schema_name='acme',
        company_name='Acme',
        requester_user_id=uuid4(),
        requester_username='op',
        requester_display_name='Operator',
        motive='Need help with receiving',
        status=c.STATUS_QUEUED,
        accepted_by_id=None,
        accepted_by_label='',
        client_unread_count=0,
        agent_unread_count=0,
        rating=None,
        rating_comment='',
        queued_at=_now(),
        accepted_at=None,
        closed_at=None,
        rated_at=None,
        updated_at=_now(),
    )
    base.update(overrides)
    return SupportSessionView(**base)


class _FakeRepo(ISupportSessionRepository):
    def __init__(self):
        self.sessions: dict = {}
        self.messages: list = []
        self.events: list = []

    def create_session(self, data, *, ask_motive_message: str) -> SupportSessionView:
        for s in self.sessions.values():
            if (
                s.requester_user_id == data.requester_user_id
                and s.status in c.OPEN_STATUSES
            ):
                raise ConflictException(AppErrorCode.SSES_ALREADY_OPEN)
        view = _session(
            company_id=data.company_id,
            schema_name=data.schema_name,
            company_name=data.company_name,
            requester_user_id=data.requester_user_id,
            requester_username=data.requester_username,
            requester_display_name=data.requester_display_name,
            motive=data.motive,
            status=c.STATUS_QUEUED,
        )
        self.sessions[view.id] = view
        self.messages.append(
            SupportSessionMessageView(
                id=uuid4(),
                session_id=view.id,
                sender_kind='SYSTEM',
                sender_user_id=None,
                body=ask_motive_message,
                created_at=_now(),
            )
        )
        self.messages.append(
            SupportSessionMessageView(
                id=uuid4(),
                session_id=view.id,
                sender_kind='CLIENT',
                sender_user_id=data.requester_user_id,
                body=data.motive,
                created_at=_now(),
            )
        )
        return view

    def get(self, session_id):
        return self.sessions.get(session_id)

    def get_open_for_requester(self, requester_user_id):
        for s in self.sessions.values():
            if s.requester_user_id == requester_user_id and s.status in c.OPEN_STATUSES:
                return s
        return None

    def get_active_for_agent(self, admin_user_id):
        for s in self.sessions.values():
            if s.accepted_by_id == admin_user_id and s.status == c.STATUS_ACTIVE:
                return s
        return None

    def list_sessions(self, filters, *, limit, offset):
        rows = list(self.sessions.values())
        return rows[offset:offset + limit], len(rows)

    def accept(self, session_id, *, admin_user_id, admin_label, system_message):
        s = self.sessions.get(session_id)
        if s is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        busy = self.get_active_for_agent(admin_user_id)
        if busy is not None and busy.id != session_id:
            raise ConflictException(AppErrorCode.SSES_AGENT_BUSY)
        if s.status != c.STATUS_QUEUED:
            raise ConflictException(AppErrorCode.SSES_ALREADY_ACCEPTED)
        updated = s.model_copy(update={
            'status': c.STATUS_ACTIVE,
            'accepted_by_id': admin_user_id,
            'accepted_by_label': admin_label,
            'accepted_at': _now(),
        })
        self.sessions[session_id] = updated
        self.messages.append(
            SupportSessionMessageView(
                id=uuid4(),
                session_id=session_id,
                sender_kind='SYSTEM',
                body=system_message,
                created_at=_now(),
            )
        )
        return updated

    def add_message(
        self,
        session_id,
        *,
        sender_kind,
        sender_user_id,
        body,
        bump_client_unread=False,
        bump_agent_unread=False,
    ):
        s = self.sessions[session_id]
        updates = {}
        if bump_client_unread:
            updates['client_unread_count'] = s.client_unread_count + 1
        if bump_agent_unread:
            updates['agent_unread_count'] = s.agent_unread_count + 1
        if updates:
            self.sessions[session_id] = s.model_copy(update=updates)
        msg = SupportSessionMessageView(
            id=uuid4(),
            session_id=session_id,
            sender_kind=sender_kind,
            sender_user_id=sender_user_id,
            body=body,
            created_at=_now(),
        )
        self.messages.append(msg)
        return msg

    def list_messages(self, session_id, *, limit, offset):
        rows = [m for m in self.messages if m.session_id == session_id]
        return rows[offset:offset + limit], len(rows)

    def list_events(self, session_id, *, limit, offset):
        rows = [e for e in self.events if e.session_id == session_id]
        return rows[offset:offset + limit], len(rows)

    def add_event(
        self,
        session_id,
        *,
        event_type,
        actor_kind='',
        actor_user_id=None,
        actor_label='',
        payload=None,
    ):
        evt = SupportSessionEventView(
            id=uuid4(),
            session_id=session_id,
            event_type=event_type,
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            payload=payload or {},
            created_at=_now(),
        )
        self.events.append(evt)
        return evt

    def mark_read_client(self, session_id):
        s = self.sessions[session_id]
        updated = s.model_copy(update={'client_unread_count': 0})
        self.sessions[session_id] = updated
        return updated

    def mark_read_agent(self, session_id):
        s = self.sessions[session_id]
        updated = s.model_copy(update={'agent_unread_count': 0})
        self.sessions[session_id] = updated
        return updated

    def cancel(self, session_id):
        s = self.sessions[session_id]
        updated = s.model_copy(update={
            'status': c.STATUS_CANCELLED,
            'closed_at': _now(),
            'client_unread_count': 0,
            'agent_unread_count': 0,
        })
        self.sessions[session_id] = updated
        return updated

    def close_for_rating(self, session_id, *, system_message):
        s = self.sessions[session_id]
        updated = s.model_copy(update={
            'status': c.STATUS_AWAITING_RATING,
            'closed_at': _now(),
        })
        self.sessions[session_id] = updated
        self.messages.append(
            SupportSessionMessageView(
                id=uuid4(),
                session_id=session_id,
                sender_kind='SYSTEM',
                body=system_message,
                created_at=_now(),
            )
        )
        return updated

    def rate(self, session_id, *, rating, comment):
        s = self.sessions[session_id]
        updated = s.model_copy(update={
            'status': c.STATUS_CLOSED,
            'rating': rating,
            'rating_comment': comment,
            'rated_at': _now(),
            'client_unread_count': 0,
            'agent_unread_count': 0,
        })
        self.sessions[session_id] = updated
        return updated

    def cancel_expired_queued(self, *, older_than_minutes: int):
        cutoff = _now() - timedelta(minutes=older_than_minutes)
        cancelled = []
        for sid, s in list(self.sessions.items()):
            if s.status == c.STATUS_QUEUED and s.queued_at < cutoff:
                updated = self.cancel(sid)
                cancelled.append(updated)
        return cancelled

    def close_stale_awaiting_rating(self, *, older_than_hours: int):
        cutoff = _now() - timedelta(hours=older_than_hours)
        closed = []
        for sid, s in list(self.sessions.items()):
            if (
                s.status == c.STATUS_AWAITING_RATING
                and s.closed_at is not None
                and s.closed_at < cutoff
            ):
                updated = s.model_copy(update={'status': c.STATUS_CLOSED})
                self.sessions[sid] = updated
                closed.append(updated)
        return closed


class _FakeSettingsRepo(ISupportSettingsRepository):
    def __init__(self, settings: Optional[SupportSettingsSchema] = None):
        self.settings = settings

    def get(self):
        return self.settings

    def save(self, data):
        self.settings = data
        return data


class _FakeNotifier(ISupportSessionNotifier):
    def __init__(self):
        self.queued = []
        self.accepted = []

    def notify_queued(self, session):
        self.queued.append(session)

    def notify_accepted(self, session, *, exclude_admin_id):
        self.accepted.append((session, exclude_admin_id))


class _FakeRealtime(ISupportSessionRealtime):
    def __init__(self):
        self.events = []

    def push_session(self, session, *, event_type, extra=None):
        self.events.append(('session', event_type, session.id))

    def push_message(self, session, message):
        self.events.append(('message', message.id, session.id))


class CreateSupportSessionTests(TestCase):
    def test_creates_and_notifies(self):
        repo, notifier, realtime = _FakeRepo(), _FakeNotifier(), _FakeRealtime()
        requester = uuid4()
        session = CreateSupportSessionUseCase(repo, notifier, realtime).execute(
            CreateSupportSessionSchema(
                motive='Help with picking',
                company_id='c1',
                schema_name='acme',
                company_name='Acme',
                requester_user_id=requester,
                requester_username='op',
                requester_display_name='Operator',
            )
        )
        self.assertEqual(session.status, c.STATUS_QUEUED)
        self.assertEqual(len(notifier.queued), 1)
        self.assertEqual(repo.messages[0].body, ASK_MOTIVE_MESSAGE)
        self.assertEqual(repo.messages[0].sender_kind, 'SYSTEM')
        self.assertEqual(repo.messages[1].body, 'Help with picking')
        self.assertEqual(repo.messages[1].sender_kind, 'CLIENT')

    def test_rejects_second_open_session(self):
        repo, notifier, realtime = _FakeRepo(), _FakeNotifier(), _FakeRealtime()
        requester = uuid4()
        data = CreateSupportSessionSchema(
            motive='One',
            company_id='c1',
            schema_name='acme',
            requester_user_id=requester,
        )
        CreateSupportSessionUseCase(repo, notifier, realtime).execute(data)
        with self.assertRaises(ConflictException) as ctx:
            CreateSupportSessionUseCase(repo, notifier, realtime).execute(
                data.model_copy(update={'motive': 'Two'})
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.SSES_ALREADY_OPEN)


class AcceptSupportSessionTests(TestCase):
    def test_first_accept_wins(self):
        repo, notifier, realtime = _FakeRepo(), _FakeNotifier(), _FakeRealtime()
        session = repo.create_session(
            CreateSupportSessionSchema(
                motive='Help',
                company_id='c1',
                schema_name='acme',
                requester_user_id=uuid4(),
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        agent = uuid4()
        accepted = AcceptSupportSessionUseCase(repo, notifier, realtime).execute(
            session.id,
            AcceptSupportSessionSchema(admin_user_id=agent, admin_label='Ada'),
        )
        self.assertEqual(accepted.status, c.STATUS_ACTIVE)
        self.assertEqual(accepted.accepted_by_id, agent)
        self.assertTrue(any(m.body == AGENT_JOINED_MESSAGE for m in repo.messages))

        with self.assertRaises(ConflictException) as ctx:
            AcceptSupportSessionUseCase(repo, notifier, realtime).execute(
                session.id,
                AcceptSupportSessionSchema(admin_user_id=uuid4(), admin_label='Bob'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.SSES_ALREADY_ACCEPTED)

    def test_agent_busy_rejects_second_accept(self):
        repo, notifier, realtime = _FakeRepo(), _FakeNotifier(), _FakeRealtime()
        agent = uuid4()
        first = repo.create_session(
            CreateSupportSessionSchema(
                motive='One',
                company_id='c1',
                schema_name='acme',
                requester_user_id=uuid4(),
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        second = repo.create_session(
            CreateSupportSessionSchema(
                motive='Two',
                company_id='c1',
                schema_name='acme',
                requester_user_id=uuid4(),
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        AcceptSupportSessionUseCase(repo, notifier, realtime).execute(
            first.id,
            AcceptSupportSessionSchema(admin_user_id=agent, admin_label='Ada'),
        )
        with self.assertRaises(ConflictException) as ctx:
            AcceptSupportSessionUseCase(repo, notifier, realtime).execute(
                second.id,
                AcceptSupportSessionSchema(admin_user_id=agent, admin_label='Ada'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.SSES_AGENT_BUSY)


class MessageAndCloseTests(TestCase):
    def _active(self):
        repo, notifier, realtime = _FakeRepo(), _FakeNotifier(), _FakeRealtime()
        requester = uuid4()
        agent = uuid4()
        session = repo.create_session(
            CreateSupportSessionSchema(
                motive='Help',
                company_id='c1',
                schema_name='acme',
                requester_user_id=requester,
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        AcceptSupportSessionUseCase(repo, notifier, realtime).execute(
            session.id,
            AcceptSupportSessionSchema(admin_user_id=agent, admin_label='Ada'),
        )
        return repo, realtime, session.id, requester, agent

    def test_agent_message_bumps_client_unread(self):
        repo, realtime, sid, requester, agent = self._active()
        SendAgentMessageUseCase(repo, realtime).execute(
            sid,
            admin_user_id=agent,
            data=SendSupportMessageSchema(body='Hello'),
        )
        self.assertEqual(repo.get(sid).client_unread_count, 1)

    def test_client_message_bumps_agent_unread(self):
        repo, realtime, sid, requester, agent = self._active()
        SendClientMessageUseCase(repo, realtime).execute(
            sid,
            requester_user_id=requester,
            data=SendSupportMessageSchema(body='More detail'),
        )
        self.assertEqual(repo.get(sid).agent_unread_count, 1)

    def test_close_then_rate(self):
        repo, realtime, sid, requester, agent = self._active()
        CloseSupportSessionUseCase(repo, realtime).execute(sid, admin_user_id=agent)
        self.assertEqual(repo.get(sid).status, c.STATUS_AWAITING_RATING)
        closed = RateSupportSessionUseCase(repo, realtime).execute(
            sid,
            requester_user_id=requester,
            data=RateSupportSessionSchema(rating=5, comment='Great'),
        )
        self.assertEqual(closed.status, c.STATUS_CLOSED)
        self.assertEqual(closed.rating, 5)

    def test_cancel_only_when_queued(self):
        repo, realtime = _FakeRepo(), _FakeRealtime()
        requester = uuid4()
        session = repo.create_session(
            CreateSupportSessionSchema(
                motive='Help',
                company_id='c1',
                schema_name='acme',
                requester_user_id=requester,
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        CancelSupportSessionUseCase(repo, realtime).execute(
            session.id,
            requester_user_id=requester,
        )
        self.assertEqual(repo.get(session.id).status, c.STATUS_CANCELLED)

    def test_cancel_rejected_when_active(self):
        repo, realtime, sid, requester, agent = self._active()
        with self.assertRaises(ConflictException):
            CancelSupportSessionUseCase(repo, realtime).execute(
                sid,
                requester_user_id=requester,
            )

    def test_wrong_agent_cannot_message(self):
        repo, realtime, sid, requester, agent = self._active()
        with self.assertRaises(ConflictException) as ctx:
            SendAgentMessageUseCase(repo, realtime).execute(
                sid,
                admin_user_id=uuid4(),
                data=SendSupportMessageSchema(body='Nope'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.SSES_NOT_ASSIGNED)

    def test_missing_session(self):
        repo, realtime = _FakeRepo(), _FakeRealtime()
        with self.assertRaises(NotFoundException):
            SendClientMessageUseCase(repo, realtime).execute(
                uuid4(),
                requester_user_id=uuid4(),
                data=SendSupportMessageSchema(body='x'),
            )

    def test_list_messages_enforces_ownership(self):
        repo, realtime, sid, requester, agent = self._active()
        items, total = ListSupportMessagesUseCase(repo).execute(
            sid, limit=50, offset=0, requester_user_id=requester,
        )
        self.assertGreater(total, 0)
        with self.assertRaises(NotFoundException):
            ListSupportMessagesUseCase(repo).execute(
                sid, limit=50, offset=0, requester_user_id=uuid4(),
            )


class SupportSettingsTests(TestCase):
    def test_empty_patch_rejected(self):
        settings_repo = _FakeSettingsRepo(SupportSettingsSchema())
        with self.assertRaises(ValidationAppException) as ctx:
            UpdateSupportSettingsUseCase(settings_repo).execute(
                UpdateSupportSettingsSchema(),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)

    def test_valid_whatsapp_url_saved(self):
        settings_repo = _FakeSettingsRepo(SupportSettingsSchema())
        updated = UpdateSupportSettingsUseCase(settings_repo).execute(
            UpdateSupportSettingsSchema(
                whatsapp_url='https://wa.me/573001112233',
                phone_line='+57 300 111 2233',
            ),
        )
        self.assertEqual(updated.whatsapp_url, 'https://wa.me/573001112233')
        self.assertEqual(updated.phone_line, '+57 300 111 2233')

    def test_invalid_whatsapp_url_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateSupportSettingsSchema(whatsapp_url='javascript:alert(1)')
        with self.assertRaises(ValidationError):
            UpdateSupportSettingsSchema(whatsapp_url='not-a-url')
        self.assertEqual(normalize_whatsapp_url(''), '')
        self.assertEqual(
            normalize_whatsapp_url('https://wa.me/1'),
            'https://wa.me/1',
        )


class ExpireStaleTests(TestCase):
    def test_expires_old_queued_and_awaiting_rating(self):
        repo, realtime = _FakeRepo(), _FakeRealtime()
        settings_repo = _FakeSettingsRepo(
            SupportSettingsSchema(queue_wait_timeout_minutes=10),
        )
        old_queued = repo.create_session(
            CreateSupportSessionSchema(
                motive='Old queue',
                company_id='c1',
                schema_name='acme',
                requester_user_id=uuid4(),
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        repo.sessions[old_queued.id] = old_queued.model_copy(
            update={'queued_at': _now() - timedelta(minutes=30)},
        )

        agent = uuid4()
        requester = uuid4()
        active = repo.create_session(
            CreateSupportSessionSchema(
                motive='Active then closed',
                company_id='c1',
                schema_name='acme',
                requester_user_id=requester,
            ),
            ask_motive_message=ASK_MOTIVE_MESSAGE,
        )
        AcceptSupportSessionUseCase(repo, _FakeNotifier(), realtime).execute(
            active.id,
            AcceptSupportSessionSchema(admin_user_id=agent, admin_label='Ada'),
        )
        CloseSupportSessionUseCase(repo, realtime).execute(
            active.id, admin_user_id=agent,
        )
        awaiting = repo.get(active.id)
        repo.sessions[active.id] = awaiting.model_copy(
            update={'closed_at': _now() - timedelta(hours=c.AWAITING_RATING_TTL_HOURS + 1)},
        )

        result = ExpireStaleSupportSessionsUseCase(
            repo, settings_repo, realtime,
        ).execute()
        self.assertEqual(result['cancelled_queued'], 1)
        self.assertEqual(result['closed_awaiting_rating'], 1)
        self.assertEqual(repo.get(old_queued.id).status, c.STATUS_CANCELLED)
        self.assertEqual(repo.get(active.id).status, c.STATUS_CLOSED)
        self.assertTrue(
            any(e[1] == 'support.closed' for e in realtime.events),
        )
