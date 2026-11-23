"""
Unit tests for EmailSender CRUD use cases.

No database required — pure logic tests with mocked repository.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors.exceptions import AppException
from core.errors.codes import AppErrorCode
from platform.features.communication.email.email_sender.application.use_cases import (
    GetAllEmailSendersUseCase,
    GetEmailSenderByIdUseCase,
    CreateEmailSenderUseCase,
    UpdateEmailSenderUseCase,
    DeleteEmailSenderUseCase,
)
from platform.features.communication.email.email_sender.domain.schemas import (
    CreateEmailSenderSchema,
    EmailSenderSchema,
    UpdateEmailSenderSchema,
)


def _sender(**overrides) -> EmailSenderSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='DEFAULT',
        name='Main Sender',
        email='noreply@example.com',
        reply_to='support@example.com',
        is_default=False,
        is_active=True,
    )
    defaults.update(overrides)
    return EmailSenderSchema(**defaults)


# ── GetAllEmailSendersUseCase ─────────────────────────────────────────────────

class TestGetAllEmailSenders(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetAllEmailSendersUseCase(self.repo)

    def test_returns_list_from_repository(self):
        expected = [_sender(), _sender(code='SECOND')]
        self.repo.get_all.return_value = expected
        result = self.uc.execute()
        self.assertEqual(result, expected)

    def test_returns_empty_list_when_no_senders(self):
        self.repo.get_all.return_value = []
        self.assertEqual(self.uc.execute(), [])

    def test_delegates_to_repository(self):
        self.repo.get_all.return_value = []
        self.uc.execute()
        self.repo.get_all.assert_called_once()


# ── GetEmailSenderByIdUseCase ─────────────────────────────────────────────────

class TestGetEmailSenderById(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetEmailSenderByIdUseCase(self.repo)

    def test_returns_sender_when_found(self):
        sender = _sender()
        self.repo.get_by_id.return_value = sender
        result = self.uc.execute(sender.id)
        self.assertEqual(result, sender)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(AppException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_SENDER_NOT_FOUND)

    def test_passes_id_to_repository(self):
        sid = uuid.uuid4()
        self.repo.get_by_id.return_value = _sender(id=sid)
        self.uc.execute(sid)
        self.repo.get_by_id.assert_called_once_with(sid)


# ── CreateEmailSenderUseCase ──────────────────────────────────────────────────

class TestCreateEmailSender(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateEmailSenderUseCase(self.repo)

    def _data(self, **overrides):
        defaults = dict(
            code='NEW_SENDER',
            name='New Sender',
            email='new@example.com',
            reply_to='',
            is_default=False,
            is_active=True,
        )
        defaults.update(overrides)
        return CreateEmailSenderSchema(**defaults)

    def test_creates_sender_successfully(self):
        data = self._data()
        expected = _sender(code=data.code)
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected

        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_raises_duplicate_when_code_exists(self):
        data = self._data(code='EXISTING')
        self.repo.get_by_code.return_value = _sender(code='EXISTING')

        with self.assertRaises(AppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_SENDER_DUPLICATE)

    def test_checks_code_uniqueness_before_create(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _sender()

        self.uc.execute(data)
        self.repo.get_by_code.assert_called_once_with(data.code)

    def test_clears_existing_default_when_is_default(self):
        old_default = _sender(is_default=True)
        self.repo.get_by_code.return_value = None
        self.repo.get_all.return_value = [old_default]
        self.repo.create.return_value = _sender(is_default=True)

        data = self._data(is_default=True)
        self.uc.execute(data)

        self.repo.update.assert_called_once_with(old_default, {'is_default': False})

    def test_does_not_clear_default_when_not_default(self):
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _sender()

        data = self._data(is_default=False)
        self.uc.execute(data)

        self.repo.get_all.assert_not_called()

    def test_passes_model_dump_to_repository(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _sender()

        self.uc.execute(data)
        self.repo.create.assert_called_once_with(data.model_dump())


# ── UpdateEmailSenderUseCase ──────────────────────────────────────────────────

class TestUpdateEmailSender(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateEmailSenderUseCase(self.repo)

    def test_updates_sender_successfully(self):
        sender = _sender(code='OLD')
        updated = _sender(code='OLD', name='Updated')
        self.repo.get_by_id.return_value = sender
        self.repo.update.return_value = updated

        data = UpdateEmailSenderSchema(name='Updated')
        result = self.uc.execute(sender.id, data)
        self.assertEqual(result, updated)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None
        data = UpdateEmailSenderSchema(name='X')

        with self.assertRaises(AppException) as ctx:
            self.uc.execute(uuid.uuid4(), data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_SENDER_NOT_FOUND)

    def test_raises_duplicate_when_new_code_conflicts(self):
        sender = _sender(code='ORIGINAL')
        self.repo.get_by_id.return_value = sender
        self.repo.get_by_code.return_value = _sender(code='TAKEN')

        data = UpdateEmailSenderSchema(code='TAKEN')
        with self.assertRaises(AppException) as ctx:
            self.uc.execute(sender.id, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_SENDER_DUPLICATE)

    def test_allows_keeping_same_code(self):
        sender = _sender(code='SAME')
        self.repo.get_by_id.return_value = sender
        self.repo.update.return_value = sender

        data = UpdateEmailSenderSchema(code='SAME')
        self.uc.execute(sender.id, data)
        self.repo.get_by_code.assert_not_called()

    def test_clears_other_defaults_when_setting_default(self):
        sender = _sender(is_default=False)
        other = _sender(is_default=True)
        self.repo.get_by_id.return_value = sender
        self.repo.get_all.return_value = [sender, other]
        self.repo.update.return_value = sender

        data = UpdateEmailSenderSchema(is_default=True)
        self.uc.execute(sender.id, data)

        self.repo.update.assert_any_call(other, {'is_default': False})

    def test_does_not_clear_own_default(self):
        sender = _sender(is_default=True)
        self.repo.get_by_id.return_value = sender
        self.repo.get_all.return_value = [sender]
        self.repo.update.return_value = sender

        data = UpdateEmailSenderSchema(is_default=True)
        self.uc.execute(sender.id, data)

        # update called once for the main update, not for clearing itself
        calls_with_false = [c for c in self.repo.update.call_args_list if c == ((sender, {'is_default': False}),)]
        self.assertEqual(len(calls_with_false), 0)

    def test_excludes_none_fields_from_changes(self):
        sender = _sender()
        self.repo.get_by_id.return_value = sender
        self.repo.update.return_value = sender

        data = UpdateEmailSenderSchema(name='Only Name')
        self.uc.execute(sender.id, data)

        _, kwargs = self.repo.update.call_args
        if not kwargs:
            args = self.repo.update.call_args[0]
            changes = args[1]
        else:
            changes = kwargs
        self.assertIn('name', changes)


# ── DeleteEmailSenderUseCase ──────────────────────────────────────────────────

class TestDeleteEmailSender(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = DeleteEmailSenderUseCase(self.repo)

    def test_deletes_sender_successfully(self):
        sender = _sender()
        self.repo.get_by_id.return_value = sender
        self.uc.execute(sender.id)
        self.repo.delete.assert_called_once_with(sender)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None

        with self.assertRaises(AppException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_SENDER_NOT_FOUND)

    def test_does_not_delete_when_not_found(self):
        self.repo.get_by_id.return_value = None
        try:
            self.uc.execute(uuid.uuid4())
        except AppException:
            pass
        self.repo.delete.assert_not_called()
