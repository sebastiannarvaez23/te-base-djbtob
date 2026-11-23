"""
Unit tests for EmailTemplate CRUD use cases.

No database required — pure logic tests with mocked repository.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors.exceptions import ConflictException
from core.errors.codes import AppErrorCode
from platform.features.communication.email.email_template.application.use_cases import (
    GetAllEmailTemplatesUseCase,
    GetEmailTemplateByIdUseCase,
    CreateEmailTemplateUseCase,
    UpdateEmailTemplateUseCase,
    DeleteEmailTemplateUseCase,
)
from platform.features.communication.email.email_template.domain.schemas import (
    CreateEmailTemplateSchema,
    EmailTemplateSchema,
    UpdateEmailTemplateSchema,
)


def _template(**overrides) -> EmailTemplateSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='WELCOME',
        name='Welcome Email',
        subject='Welcome {{ user_name }}',
        body='Hello {{ user_name }}',
        html_template='<h1>Welcome {{ user_name }}</h1>',
        sender=None,
        mock_data={'user_name': 'John'},
        description='Welcome email template',
        is_active=True,
    )
    defaults.update(overrides)
    return EmailTemplateSchema(**defaults)


# ── GetAllEmailTemplatesUseCase ───────────────────────────────────────────────

class TestGetAllEmailTemplates(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetAllEmailTemplatesUseCase(self.repo)

    def test_returns_all_templates(self):
        expected = [_template(), _template(code='RESET')]
        self.repo.get_all.return_value = expected
        result = self.uc.execute()
        self.assertEqual(result, expected)

    def test_returns_empty_list(self):
        self.repo.get_all.return_value = []
        self.assertEqual(self.uc.execute(), [])

    def test_delegates_to_repository(self):
        self.repo.get_all.return_value = []
        self.uc.execute()
        self.repo.get_all.assert_called_once()


# ── GetEmailTemplateByIdUseCase ───────────────────────────────────────────────

class TestGetEmailTemplateById(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetEmailTemplateByIdUseCase(self.repo)

    def test_returns_template_when_found(self):
        tpl = _template()
        self.repo.get_by_id.return_value = tpl
        result = self.uc.execute(tpl.id)
        self.assertEqual(result, tpl)

    def test_returns_none_when_not_found(self):
        self.repo.get_by_id.return_value = None
        result = self.uc.execute(uuid.uuid4())
        self.assertIsNone(result)

    def test_passes_id_to_repository(self):
        tid = uuid.uuid4()
        self.repo.get_by_id.return_value = _template(id=tid)
        self.uc.execute(tid)
        self.repo.get_by_id.assert_called_once_with(tid)


# ── CreateEmailTemplateUseCase ────────────────────────────────────────────────

class TestCreateEmailTemplate(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateEmailTemplateUseCase(self.repo)

    def _data(self, **overrides):
        defaults = dict(
            code='NEW_TPL',
            name='New Template',
            subject='Subject',
            html_template='<p>Body</p>',
        )
        defaults.update(overrides)
        return CreateEmailTemplateSchema(**defaults)

    def test_creates_template_successfully(self):
        data = self._data()
        expected = _template(code=data.code)
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected

        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_raises_conflict_when_code_exists(self):
        data = self._data(code='EXISTING')
        self.repo.get_by_code.return_value = _template(code='EXISTING')

        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_DUPLICATE_CODE)

    def test_checks_code_uniqueness(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _template()

        self.uc.execute(data)
        self.repo.get_by_code.assert_called_once_with(data.code)

    def test_passes_schema_to_repository_create(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _template()

        self.uc.execute(data)
        self.repo.create.assert_called_once_with(data)


# ── UpdateEmailTemplateUseCase ────────────────────────────────────────────────

class TestUpdateEmailTemplate(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateEmailTemplateUseCase(self.repo)

    def test_updates_template_successfully(self):
        tid = uuid.uuid4()
        updated = _template(id=tid, name='Updated')
        self.repo.get_by_code.return_value = None
        self.repo.update.return_value = updated

        data = UpdateEmailTemplateSchema(name='Updated')
        result = self.uc.execute(tid, data)
        self.assertEqual(result, updated)

    def test_raises_conflict_when_new_code_taken_by_other(self):
        tid = uuid.uuid4()
        other_id = uuid.uuid4()
        self.repo.get_by_code.return_value = _template(id=other_id, code='TAKEN')

        data = UpdateEmailTemplateSchema(code='TAKEN')
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(tid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_DUPLICATE_CODE)

    def test_allows_keeping_same_code(self):
        tid = uuid.uuid4()
        self.repo.get_by_code.return_value = _template(id=tid, code='SAME')
        self.repo.update.return_value = _template(id=tid)

        data = UpdateEmailTemplateSchema(code='SAME')
        self.uc.execute(tid, data)
        self.repo.update.assert_called_once_with(tid, data)

    def test_skips_code_check_when_code_not_in_update(self):
        tid = uuid.uuid4()
        self.repo.update.return_value = _template(id=tid)

        data = UpdateEmailTemplateSchema(name='Only Name')
        self.uc.execute(tid, data)
        self.repo.get_by_code.assert_not_called()

    def test_passes_id_and_data_to_repository(self):
        tid = uuid.uuid4()
        self.repo.update.return_value = _template(id=tid)

        data = UpdateEmailTemplateSchema(subject='New Subject')
        self.uc.execute(tid, data)
        self.repo.update.assert_called_once_with(tid, data)


# ── DeleteEmailTemplateUseCase ────────────────────────────────────────────────

class TestDeleteEmailTemplate(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = DeleteEmailTemplateUseCase(self.repo)

    def test_deletes_template(self):
        tid = uuid.uuid4()
        self.repo.delete.return_value = True
        result = self.uc.execute(tid)
        self.assertTrue(result)

    def test_returns_false_when_not_found(self):
        self.repo.delete.return_value = False
        result = self.uc.execute(uuid.uuid4())
        self.assertFalse(result)

    def test_passes_id_to_repository(self):
        tid = uuid.uuid4()
        self.repo.delete.return_value = True
        self.uc.execute(tid)
        self.repo.delete.assert_called_once_with(tid)
