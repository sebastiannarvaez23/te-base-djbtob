"""Unit tests for testimonial prompt settings, frequency, and reprompt."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from core.errors import ValidationAppException
from core.errors.codes import AppErrorCode
from platform.features.configuration.landing.testimonial.application.prompt_use_cases import (
    AckTestimonialPromptUseCase,
    DecideTestimonialPromptUseCase,
    GetTestimonialPromptSettingsUseCase,
    RecordTestimonialPromptSeenUseCase,
    RepromptTestimonialsUseCase,
    UpdateTestimonialPromptSettingsUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    RepromptTestimonialsSchema,
    TestimonialPromptReceiptSchema,
    TestimonialPromptSettingsSchema,
    TestimonialSchema,
    UpdateTestimonialPromptSettingsSchema,
)
from platform.features.configuration.landing.testimonial.presentation.bodies import (
    RepromptTestimonialsBody,
    UpdateTestimonialPromptSettingsBody,
)
from platform.features.configuration.landing.testimonial.presentation.queries import (
    TestimonialListQuery,
)

pytestmark = pytest.mark.unit

USER_ID = uuid.uuid4()
ROW_ID = uuid.uuid4()


def _settings(**overrides) -> TestimonialPromptSettingsSchema:
    defaults = dict(
        prompt_enabled=True,
        frequency_days=30,
        ask_after_submit=False,
    )
    defaults.update(overrides)
    return TestimonialPromptSettingsSchema(**defaults)


def _receipt(**overrides) -> TestimonialPromptReceiptSchema:
    defaults = dict(
        user_id=USER_ID,
        last_prompted_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return TestimonialPromptReceiptSchema(**defaults)


def _row(**overrides) -> TestimonialSchema:
    defaults = dict(
        id=ROW_ID,
        author_id=USER_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        author_name='María Restrepo',
        company_name='Distribuidora Andina',
        locale='es',
        is_published=True,
        seal='',
        signed_at=None,
    )
    defaults.update(overrides)
    return TestimonialSchema(**defaults)


def _settings_repo(current=None):
    repo = MagicMock()
    repo.get.return_value = current
    repo.save.side_effect = lambda data: data
    return repo


def _receipts_repo(current=None):
    repo = MagicMock()
    repo.get.return_value = current
    repo.upsert.side_effect = lambda data: data
    return repo


def _testimonials_repo(row=None):
    repo = MagicMock()
    repo.get_by_author.return_value = row
    return repo


class TestPromptSettingsSchema(TestCase):

    def test_rejects_frequency_above_year(self):
        with self.assertRaises(ValidationError):
            TestimonialPromptSettingsSchema(frequency_days=366)

    def test_rejects_login_delay_above_cap(self):
        with self.assertRaises(ValidationError):
            TestimonialPromptSettingsSchema(login_delay_seconds=301)

    def test_accepts_every_login(self):
        data = TestimonialPromptSettingsSchema(frequency_days=0)
        self.assertEqual(data.frequency_days, 0)


class TestUpdatePromptSettingsBody(TestCase):

    def test_accepts_partial_patch(self):
        ok, errors = UpdateTestimonialPromptSettingsBody({
            'frequency_days': 15,
            'first_appearance_days': 3,
            'login_delay_seconds': 10,
        }).validate()
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_rejects_unknown_field(self):
        ok, errors = UpdateTestimonialPromptSettingsBody({
            'prompt_enabled': True,
            'extra': True,
        }).validate()
        self.assertFalse(ok)


class TestRepromptTestimonialsBody(TestCase):

    def test_accepts_author_ids(self):
        author_id = str(uuid.uuid4())
        ok, errors = RepromptTestimonialsBody({
            'author_ids': [author_id],
        }).validate()
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_dedupes_author_ids(self):
        author_id = str(uuid.uuid4())
        body = RepromptTestimonialsBody({
            'author_ids': [author_id, author_id],
        })
        ok, errors = body.validate()
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(body.validated_data['author_ids'], [uuid.UUID(author_id)])

    def test_rejects_empty_list(self):
        ok, errors = RepromptTestimonialsBody({'author_ids': []}).validate()
        self.assertFalse(ok)

    def test_rejects_invalid_uuid(self):
        ok, errors = RepromptTestimonialsBody({
            'author_ids': ['not-a-uuid'],
        }).validate()
        self.assertFalse(ok)


class TestTestimonialListQuerySigned(TestCase):

    def test_accepts_signed_filter(self):
        query, err = TestimonialListQuery({'signed': 'true'}).parse()
        self.assertIsNone(err)
        self.assertTrue(query.filters['signed'])


class TestGetPromptSettingsUseCase(TestCase):

    def test_returns_defaults_when_missing_without_writing(self):
        repo = _settings_repo(None)
        result = GetTestimonialPromptSettingsUseCase(repo).execute()
        repo.save.assert_not_called()
        self.assertTrue(result.prompt_enabled)
        self.assertEqual(result.frequency_days, 30)
        self.assertEqual(result.first_appearance_days, 0)
        self.assertEqual(result.login_delay_seconds, 0)


class TestUpdatePromptSettingsUseCase(TestCase):

    def setUp(self):
        patcher = patch(
            'platform.features.configuration.landing.testimonial.application.prompt_use_cases.invalidate_cache',
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_empty_patch(self):
        repo = _settings_repo(_settings())
        with self.assertRaises(ValidationAppException):
            UpdateTestimonialPromptSettingsUseCase(repo).execute(
                UpdateTestimonialPromptSettingsSchema(),
            )

    def test_patches_frequency(self):
        repo = _settings_repo(_settings())
        result = UpdateTestimonialPromptSettingsUseCase(repo).execute(
            UpdateTestimonialPromptSettingsSchema(frequency_days=7),
        )
        self.assertEqual(result.frequency_days, 7)
        self.assertTrue(result.prompt_enabled)

    def test_patches_first_appearance_and_login_delay(self):
        repo = _settings_repo(_settings())
        result = UpdateTestimonialPromptSettingsUseCase(repo).execute(
            UpdateTestimonialPromptSettingsSchema(
                first_appearance_days=15,
                login_delay_seconds=8,
            ),
        )
        self.assertEqual(result.first_appearance_days, 15)
        self.assertEqual(result.login_delay_seconds, 8)


class TestRepromptTestimonialsUseCase(TestCase):

    def test_marks_pending_for_rated_authors(self):
        author_a = uuid.uuid4()
        author_b = uuid.uuid4()
        testimonials = MagicMock()
        testimonials.list_by_author_ids.return_value = [
            _row(author_id=author_a, score=1),
            _row(id=uuid.uuid4(), author_id=author_b, score=3),
        ]
        receipts = MagicMock()
        receipts.mark_pending_reprompt.return_value = 2

        result = RepromptTestimonialsUseCase(testimonials, receipts).execute(
            RepromptTestimonialsSchema(author_ids=[author_a, author_b]),
        )

        self.assertEqual(result.requested, 2)
        receipts.mark_pending_reprompt.assert_called_once_with([author_a, author_b])

    def test_rejects_authors_without_testimonial(self):
        rated = uuid.uuid4()
        missing = uuid.uuid4()
        testimonials = MagicMock()
        testimonials.list_by_author_ids.return_value = [_row(author_id=rated)]
        receipts = MagicMock()

        with self.assertRaises(ValidationAppException) as ctx:
            RepromptTestimonialsUseCase(testimonials, receipts).execute(
                RepromptTestimonialsSchema(author_ids=[rated, missing]),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_REPROMPT_NOT_ELIGIBLE)
        receipts.mark_pending_reprompt.assert_not_called()


class TestDecideTestimonialPromptUseCase(TestCase):

    def _decide(self, settings, receipt=None, row=None):
        return DecideTestimonialPromptUseCase(
            _settings_repo(settings),
            _receipts_repo(receipt),
            _testimonials_repo(row),
        ).execute(USER_ID)

    def test_disabled_never_prompts(self):
        result = self._decide(_settings(prompt_enabled=False))
        self.assertFalse(result.should_prompt)
        self.assertEqual(result.delay_seconds, 0)

    def test_signed_author_is_skipped(self):
        result = self._decide(
            _settings(),
            row=_row(seal='abc', signed_at=datetime.now(timezone.utc)),
        )
        self.assertFalse(result.should_prompt)

    def test_pending_reprompt_asks_signed_author(self):
        result = self._decide(
            _settings(),
            receipt=_receipt(pending_reprompt=True),
            row=_row(seal='abc', signed_at=datetime.now(timezone.utc)),
        )
        self.assertTrue(result.should_prompt)

    def test_pending_reprompt_does_not_override_disabled(self):
        result = self._decide(
            _settings(prompt_enabled=False),
            receipt=_receipt(pending_reprompt=True),
            row=_row(seal='abc', signed_at=datetime.now(timezone.utc)),
        )
        self.assertFalse(result.should_prompt)

    def test_signed_author_can_be_asked_again(self):
        result = self._decide(
            _settings(ask_after_submit=True),
            row=_row(seal='abc', signed_at=datetime.now(timezone.utc)),
        )
        self.assertTrue(result.should_prompt)

    def test_returns_login_delay_when_prompting(self):
        result = self._decide(_settings(login_delay_seconds=12))
        self.assertTrue(result.should_prompt)
        self.assertEqual(result.delay_seconds, 12)

    def test_first_visit_prompts(self):
        result = self._decide(_settings())
        self.assertTrue(result.should_prompt)

    def test_first_appearance_without_seen_does_not_write(self):
        receipts = _receipts_repo(None)
        result = DecideTestimonialPromptUseCase(
            _settings_repo(_settings(first_appearance_days=7)),
            receipts,
            _testimonials_repo(),
        ).execute(USER_ID)
        self.assertFalse(result.should_prompt)
        receipts.upsert.assert_not_called()

    def test_first_appearance_waits_until_days_elapsed(self):
        result = self._decide(
            _settings(first_appearance_days=7),
            receipt=_receipt(
                last_prompted_at=None,
                first_seen_at=datetime.now(timezone.utc) - timedelta(days=2),
            ),
        )
        self.assertFalse(result.should_prompt)

    def test_first_appearance_prompts_after_wait(self):
        result = self._decide(
            _settings(first_appearance_days=7, login_delay_seconds=5),
            receipt=_receipt(
                last_prompted_at=None,
                first_seen_at=datetime.now(timezone.utc) - timedelta(days=8),
            ),
        )
        self.assertTrue(result.should_prompt)
        self.assertEqual(result.delay_seconds, 5)

    def test_pending_reprompt_skips_first_appearance_wait(self):
        result = self._decide(
            _settings(first_appearance_days=30),
            receipt=_receipt(
                pending_reprompt=True,
                last_prompted_at=None,
                first_seen_at=datetime.now(timezone.utc),
            ),
        )
        self.assertTrue(result.should_prompt)

    def test_frequency_zero_prompts_every_login(self):
        result = self._decide(
            _settings(frequency_days=0),
            receipt=_receipt(last_prompted_at=datetime.now(timezone.utc)),
        )
        self.assertTrue(result.should_prompt)

    def test_recent_skip_waits(self):
        result = self._decide(
            _settings(frequency_days=30),
            receipt=_receipt(last_prompted_at=datetime.now(timezone.utc) - timedelta(days=2)),
        )
        self.assertFalse(result.should_prompt)

    def test_old_skip_prompts_again(self):
        result = self._decide(
            _settings(frequency_days=7),
            receipt=_receipt(last_prompted_at=datetime.now(timezone.utc) - timedelta(days=8)),
        )
        self.assertTrue(result.should_prompt)


class TestRecordTestimonialPromptSeenUseCase(TestCase):

    def test_sets_first_seen_when_missing(self):
        receipts = _receipts_repo(None)
        result = RecordTestimonialPromptSeenUseCase(receipts).execute(USER_ID)
        receipts.upsert.assert_called_once()
        self.assertEqual(result.user_id, USER_ID)
        self.assertIsNotNone(result.first_seen_at)
        self.assertIsNone(result.last_prompted_at)

    def test_is_idempotent_when_already_seen(self):
        seen = datetime.now(timezone.utc) - timedelta(days=2)
        existing = _receipt(first_seen_at=seen, last_prompted_at=None)
        receipts = _receipts_repo(existing)
        result = RecordTestimonialPromptSeenUseCase(receipts).execute(USER_ID)
        receipts.upsert.assert_not_called()
        self.assertEqual(result.first_seen_at, seen)


class TestAckTestimonialPromptUseCase(TestCase):

    def test_clears_pending_and_stamps_last_prompted(self):
        seen = datetime.now(timezone.utc) - timedelta(days=3)
        receipts = _receipts_repo(_receipt(
            pending_reprompt=True,
            first_seen_at=seen,
            last_prompted_at=None,
        ))
        result = AckTestimonialPromptUseCase(receipts).execute(USER_ID)
        self.assertEqual(result.user_id, USER_ID)
        self.assertFalse(result.pending_reprompt)
        self.assertEqual(result.first_seen_at, seen)
        self.assertIsNotNone(result.last_prompted_at)
        receipts.upsert.assert_called_once()
