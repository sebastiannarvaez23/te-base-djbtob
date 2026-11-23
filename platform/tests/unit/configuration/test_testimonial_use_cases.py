"""Unit tests for testimonial CRUD use cases and domain schemas."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from pydantic import ValidationError

from core.errors import ConflictException, NotFoundException
from core.errors.codes import AppErrorCode
from core.signing.domain.schemas import SealVerification
from platform.features.configuration.landing.testimonial.application.use_cases import (
    CreateTestimonialUseCase,
    GetTestimonialUseCase,
    ListPublicTestimonialsUseCase,
    ListTestimonialsUseCase,
    SubmitMyTestimonialUseCase,
    UpdateTestimonialUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    AuthorSnapshot,
    CreateTestimonialSchema,
    PublicTestimonialSchema,
    SubmitMyTestimonialSchema,
    TestimonialListFilters,
    TestimonialSchema,
    UpdateTestimonialSchema,
    resolve_attribution,
)

pytestmark = pytest.mark.unit

AUTHOR_ID = uuid.uuid4()
OTHER_AUTHOR = uuid.uuid4()
ROW_ID = uuid.uuid4()


def _snapshot(**overrides) -> AuthorSnapshot:
    defaults = dict(
        id=AUTHOR_ID,
        display_name='María Restrepo',
        company_name='Distribuidora Andina',
        is_active=True,
    )
    defaults.update(overrides)
    return AuthorSnapshot(**defaults)


def _row(**overrides) -> TestimonialSchema:
    defaults = dict(
        id=ROW_ID,
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        author_name='María Restrepo',
        author_role='Jefe de Operaciones',
        company_name='Distribuidora Andina',
        locale='es',
        is_published=True,
        sort_order=1,
    )
    defaults.update(overrides)
    return TestimonialSchema(**defaults)


def _create(**overrides) -> CreateTestimonialSchema:
    defaults = dict(
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
    )
    defaults.update(overrides)
    return CreateTestimonialSchema(**defaults)


# ── Schemas ───────────────────────────────────────────────────────────────────


class TestCreateTestimonialSchema(TestCase):

    def test_accepts_valid_payload(self):
        data = _create(locale='EN', author_role='  Ops  ')
        self.assertEqual(data.locale, 'en')
        self.assertEqual(data.author_role, 'Ops')
        self.assertFalse(data.is_published)

    def test_rejects_score_below_range(self):
        with self.assertRaises(ValidationError):
            _create(score=0)

    def test_rejects_score_above_range(self):
        with self.assertRaises(ValidationError):
            _create(score=6)

    def test_rejects_blank_message(self):
        with self.assertRaises(ValidationError):
            _create(message='   ')

    def test_rejects_message_too_long(self):
        with self.assertRaises(ValidationError):
            _create(message='x' * 2001)

    def test_rejects_unknown_locale(self):
        with self.assertRaises(ValidationError):
            _create(locale='fr')

    def test_strips_optional_labels(self):
        data = _create(author_name='  Ana  ', company_name='  ')
        self.assertEqual(data.author_name, 'Ana')
        self.assertIsNone(data.company_name)


class TestSubmitMyTestimonialSchema(TestCase):

    def test_accepts_valid_payload(self):
        data = SubmitMyTestimonialSchema(
            author_id=AUTHOR_ID,
            score=5,
            message='El picking guiado cambió la operación.',
            locale='EN',
            accepted=True,
        )
        self.assertEqual(data.locale, 'en')

    def test_rejects_short_message(self):
        with self.assertRaises(ValidationError):
            SubmitMyTestimonialSchema(
                author_id=AUTHOR_ID, score=5, message='corto', accepted=True,
            )

    def test_rejects_unsigned_submit(self):
        with self.assertRaises(ValidationError):
            SubmitMyTestimonialSchema(
                author_id=AUTHOR_ID,
                score=5,
                message='El picking guiado cambió la operación.',
                accepted=False,
            )


class TestUpdateTestimonialSchema(TestCase):

    def test_partial_update_only_sets_provided_fields(self):
        data = UpdateTestimonialSchema(score=4)
        self.assertEqual(data.model_fields_set, {'score'})
        self.assertEqual(data.score, 4)

    def test_rejects_invalid_locale(self):
        with self.assertRaises(ValidationError):
            UpdateTestimonialSchema(locale='pt')

    def test_blank_message_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateTestimonialSchema(message=' ')


class TestResolveAttribution(TestCase):

    def test_uses_snapshot_when_no_override(self):
        name, company = resolve_attribution(_snapshot())
        self.assertEqual(name, 'María Restrepo')
        self.assertEqual(company, 'Distribuidora Andina')

    def test_prefers_override(self):
        name, company = resolve_attribution(
            _snapshot(), author_name='Ana Gómez', company_name='MercaPlus',
        )
        self.assertEqual(name, 'Ana Gómez')
        self.assertEqual(company, 'MercaPlus')

    def test_keeps_existing_when_override_blank(self):
        name, company = resolve_attribution(
            _snapshot(display_name='New User', company_name='New Co'),
            existing=_row(),
        )
        self.assertEqual(name, 'María Restrepo')
        self.assertEqual(company, 'Distribuidora Andina')


# ── List ──────────────────────────────────────────────────────────────────────


class TestListTestimonialsUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = ListTestimonialsUseCase(self.repo)
        patcher = patch('core.cache.decorators.caches')
        self.mock_caches = patcher.start()
        self.mock_cache = MagicMock()
        self.mock_caches.__getitem__ = MagicMock(return_value=self.mock_cache)
        self.mock_cache.get.return_value = None
        self.addCleanup(patcher.stop)

    def test_returns_rows(self):
        expected = [_row(), _row(id=uuid.uuid4(), score=4)]
        self.repo.list_page.return_value = (expected, 2)
        result = self.uc.execute(TestimonialListFilters())
        self.assertEqual(result.items, expected)
        self.assertEqual(result.total, 2)
        self.repo.list_page.assert_called_once_with(
            TestimonialListFilters(), offset=None, limit=None,
        )

    def test_passes_filters(self):
        self.repo.list_page.return_value = ([], 0)
        filters = TestimonialListFilters(locale='es', is_published=True)
        self.uc.execute(filters, offset=0, limit=20)
        self.repo.list_page.assert_called_once_with(
            filters, offset=0, limit=20,
        )

    def test_returns_empty_list(self):
        self.repo.list_page.return_value = ([], 0)
        result = self.uc.execute(TestimonialListFilters())
        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)


class TestListPublicTestimonialsUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = ListPublicTestimonialsUseCase(self.repo)
        patcher = patch('core.cache.decorators.caches')
        self.mock_caches = patcher.start()
        self.mock_cache = MagicMock()
        self.mock_caches.__getitem__ = MagicMock(return_value=self.mock_cache)
        self.mock_cache.get.return_value = None
        self.addCleanup(patcher.stop)

    def test_forces_published_signed_and_projects_public_schema(self):
        signed = _row(
            content_hash='a' * 64,
            seal='b' * 64,
            seal_algorithm='hmac-sha256-v1',
            signed_at=datetime.now(timezone.utc),
            signatory_id=str(AUTHOR_ID),
            canonical_payload='{}',
        )
        self.repo.list_page.return_value = ([signed], 1)
        with patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.hash_content',
            return_value='a' * 64,
        ), patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.verify_signature',
            return_value=SealVerification(valid=True),
        ):
            result = self.uc.execute(filters=TestimonialListFilters(locale='es'))
        self.repo.list_page.assert_called_once_with(
            TestimonialListFilters(locale='es', is_published=True, signed=True),
            offset=None,
            limit=None,
        )
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.total, 1)
        self.assertIsInstance(result.items[0], PublicTestimonialSchema)
        self.assertEqual(result.items[0].author_name, 'María Restrepo')
        self.assertEqual(result.items[0].seal_fingerprint, 'b' * 8)
        self.assertNotIn('author_id', result.items[0].model_dump())
        self.assertNotIn('seal', result.items[0].model_dump())

    def test_excludes_unsigned_rows(self):
        self.repo.list_page.return_value = ([_row()], 1)
        result = self.uc.execute(TestimonialListFilters())
        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)

    def test_excludes_tampered_seal(self):
        signed = _row(
            content_hash='a' * 64,
            seal='b' * 64,
            seal_algorithm='hmac-sha256-v1',
            signed_at=datetime.now(timezone.utc),
            signatory_id=str(AUTHOR_ID),
        )
        self.repo.list_page.return_value = ([signed], 1)
        with patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.hash_content',
            return_value='a' * 64,
        ), patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.verify_signature',
            return_value=SealVerification(valid=False, reason='seal_mismatch'),
        ):
            result = self.uc.execute(TestimonialListFilters())
            self.assertEqual(result.items, [])

    def test_excludes_hash_mismatch(self):
        signed = _row(
            content_hash='a' * 64,
            seal='b' * 64,
            seal_algorithm='hmac-sha256-v1',
            signed_at=datetime.now(timezone.utc),
            signatory_id=str(AUTHOR_ID),
        )
        self.repo.list_page.return_value = ([signed], 1)
        with patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.hash_content',
            return_value='c' * 64,
        ):
            result = self.uc.execute(TestimonialListFilters())
        self.assertEqual(result.items, [])

    def test_overwrites_caller_is_published(self):
        self.repo.list_page.return_value = ([], 0)
        self.uc.execute(filters=TestimonialListFilters(is_published=False))
        self.repo.list_page.assert_called_once_with(
            TestimonialListFilters(is_published=True, signed=True),
            offset=None,
            limit=None,
        )

    def test_empty(self):
        self.repo.list_page.return_value = ([], 0)
        result = self.uc.execute(TestimonialListFilters())
        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)


# ── Get ───────────────────────────────────────────────────────────────────────


class TestGetTestimonialUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetTestimonialUseCase(self.repo)

    def test_returns_row(self):
        row = _row()
        self.repo.get_by_id.return_value = row
        self.assertEqual(self.uc.execute(ROW_ID), row)

    def test_raises_not_found(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_NOT_FOUND)


# ── Create ────────────────────────────────────────────────────────────────────


class TestCreateTestimonialUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateTestimonialUseCase(self.repo)
        patcher = patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.invalidate_cache',
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_creates_with_snapshot_names(self):
        created = _row()
        self.repo.get_author.return_value = _snapshot(role='Jefe de Operaciones')
        self.repo.get_by_author.return_value = None
        self.repo.create.return_value = created

        result = self.uc.execute(_create())
        self.assertEqual(result, created)
        payload = self.repo.create.call_args.args[0]
        self.assertEqual(payload.author_name, 'María Restrepo')
        self.assertEqual(payload.company_name, 'Distribuidora Andina')
        self.assertEqual(payload.author_role, 'Jefe de Operaciones')

    def test_keeps_explicit_author_role(self):
        self.repo.get_author.return_value = _snapshot(role='Jefe de Operaciones')
        self.repo.get_by_author.return_value = None
        self.repo.create.return_value = _row()

        self.uc.execute(_create(author_role='Director de Bodega'))
        payload = self.repo.create.call_args.args[0]
        self.assertEqual(payload.author_role, 'Director de Bodega')

    def test_keeps_explicit_attribution(self):
        self.repo.get_author.return_value = _snapshot()
        self.repo.get_by_author.return_value = None
        self.repo.create.return_value = _row()

        self.uc.execute(_create(author_name='Ana Gómez', company_name='MercaPlus'))
        payload = self.repo.create.call_args.args[0]
        self.assertEqual(payload.author_name, 'Ana Gómez')
        self.assertEqual(payload.company_name, 'MercaPlus')

    def test_raises_when_author_missing(self):
        self.repo.get_author.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(_create())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)
        self.repo.create.assert_not_called()

    def test_raises_when_author_inactive(self):
        self.repo.get_author.return_value = _snapshot(is_active=False)
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(_create())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_INACTIVE)
        self.repo.create.assert_not_called()

    def test_raises_when_author_already_has_testimonial(self):
        self.repo.get_author.return_value = _snapshot()
        self.repo.get_by_author.return_value = _row()
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(_create())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
        self.repo.create.assert_not_called()


# ── Submit my testimonial ─────────────────────────────────────────────────────


def _submit(**overrides) -> SubmitMyTestimonialSchema:
    defaults = dict(
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        locale='es',
        accepted=True,
    )
    defaults.update(overrides)
    return SubmitMyTestimonialSchema(**defaults)


class TestSubmitMyTestimonialUseCase(TestCase):

    def setUp(self):
        settings_ctx = override_settings(SIGNING_SECRET_KEY='unit-test-signing-secret-key-32b!!')
        settings_ctx.enable()
        self.addCleanup(settings_ctx.disable)
        self.repo = MagicMock()
        self.uc = SubmitMyTestimonialUseCase(self.repo)
        patcher = patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.invalidate_cache',
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_publishes_with_snapshot_attribution_and_role(self):
        created = _row(is_published=True, sort_order=0, author_role='Jefe de Operaciones')
        self.repo.get_author.return_value = _snapshot(role='Jefe de Operaciones')
        self.repo.replace_live.return_value = created

        result = self.uc.execute(_submit())
        self.assertEqual(result, created)
        author_id, payload = self.repo.replace_live.call_args.args
        self.assertEqual(author_id, AUTHOR_ID)
        self.assertEqual(payload.author_id, AUTHOR_ID)
        self.assertEqual(payload.author_name, 'María Restrepo')
        self.assertEqual(payload.company_name, 'Distribuidora Andina')
        self.assertEqual(payload.author_role, 'Jefe de Operaciones')
        self.assertTrue(payload.is_published)
        self.assertEqual(payload.sort_order, 0)
        self.assertEqual(len(payload.seal), 64)
        self.assertEqual(payload.signatory_id, str(AUTHOR_ID))
        self.assertIsNotNone(payload.signed_at)

    def test_ignores_caller_trying_to_reuse_create_defaults(self):
        self.repo.get_author.return_value = _snapshot()
        self.repo.replace_live.return_value = _row()
        self.uc.execute(_submit(score=4, locale='en'))
        _, payload = self.repo.replace_live.call_args.args
        self.assertEqual(payload.score, 4)
        self.assertEqual(payload.locale, 'en')
        self.assertTrue(payload.is_published)

    def test_replaces_existing_signed_review(self):
        previous = _row(
            seal='b' * 64,
            signed_at=datetime.now(timezone.utc),
            message='La reseña anterior.',
            score=2,
        )
        replacement = _row(seal='c' * 64, is_published=True, score=5)
        self.repo.get_author.return_value = _snapshot()
        self.repo.replace_live.return_value = replacement

        result = self.uc.execute(_submit(message='La nueva reseña queda vigente.'))
        self.assertEqual(result, replacement)
        self.repo.create.assert_not_called()
        self.repo.update.assert_not_called()
        self.repo.replace_live.assert_called_once()
        author_id, payload = self.repo.replace_live.call_args.args
        self.assertEqual(author_id, AUTHOR_ID)
        self.assertNotEqual(payload.id, previous.id)
        self.assertEqual(payload.message, 'La nueva reseña queda vigente.')
        self.assertEqual(payload.score, 5)
        self.assertEqual(len(payload.seal), 64)
        self.assertNotEqual(payload.seal, previous.seal)
        self.assertTrue(payload.is_published)

    def test_replaces_unsigned_existing(self):
        self.repo.get_author.return_value = _snapshot()
        self.repo.replace_live.return_value = _row(seal='c' * 64, is_published=True)
        result = self.uc.execute(_submit())
        self.assertTrue(result.is_published)
        self.repo.create.assert_not_called()
        self.repo.update.assert_not_called()
        self.repo.replace_live.assert_called_once()
        author_id, payload = self.repo.replace_live.call_args.args
        self.assertEqual(author_id, AUTHOR_ID)
        self.assertNotEqual(payload.id, ROW_ID)
        self.assertEqual(len(payload.seal), 64)
        self.assertTrue(payload.is_published)

    def test_raises_when_author_inactive(self):
        self.repo.get_author.return_value = _snapshot(is_active=False)
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(_submit())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_INACTIVE)

    def test_raises_when_author_missing(self):
        self.repo.get_author.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(_submit())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)
        self.repo.create.assert_not_called()


# ── Update ────────────────────────────────────────────────────────────────────


class TestUpdateTestimonialUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateTestimonialUseCase(self.repo)
        patcher = patch(
            'platform.features.configuration.landing.testimonial.application.use_cases.invalidate_cache',
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_updates_score(self):
        self.repo.get_by_id.return_value = _row()
        updated = _row(score=4)
        self.repo.update.return_value = updated
        result = self.uc.execute(ROW_ID, UpdateTestimonialSchema(score=4))
        self.assertEqual(result.score, 4)
        self.repo.get_author.assert_not_called()

    def test_raises_when_missing(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(ROW_ID, UpdateTestimonialSchema(score=3))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_NOT_FOUND)

    def test_reassigns_author_from_snapshot(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot(
            id=OTHER_AUTHOR, display_name='Carlos Méndez', company_name='LogiSur',
        )
        self.repo.get_by_author.return_value = None
        self.repo.update.return_value = _row(author_id=OTHER_AUTHOR)

        self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=OTHER_AUTHOR))
        payload = self.repo.update.call_args.args[1]
        self.assertEqual(payload.author_name, 'Carlos Méndez')
        self.assertEqual(payload.company_name, 'LogiSur')
        self.assertEqual(payload.author_role, '')

    def test_reassigns_author_copies_snapshot_role(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot(
            id=OTHER_AUTHOR,
            display_name='Carlos Méndez',
            company_name='LogiSur',
            role='Supervisor',
        )
        self.repo.get_by_author.return_value = None
        self.repo.update.return_value = _row(author_id=OTHER_AUTHOR)

        self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=OTHER_AUTHOR))
        payload = self.repo.update.call_args.args[1]
        self.assertEqual(payload.author_role, 'Supervisor')

    def test_reassigns_author_keeps_explicit_role(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot(
            id=OTHER_AUTHOR, display_name='Carlos Méndez', company_name='LogiSur',
            role='Supervisor',
        )
        self.repo.get_by_author.return_value = None
        self.repo.update.return_value = _row(author_id=OTHER_AUTHOR)

        self.uc.execute(
            ROW_ID,
            UpdateTestimonialSchema(author_id=OTHER_AUTHOR, author_role='Gerente'),
        )
        payload = self.repo.update.call_args.args[1]
        self.assertEqual(payload.author_role, 'Gerente')

    def test_reassign_to_duplicate_author_conflicts(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot(id=OTHER_AUTHOR)
        self.repo.get_by_author.return_value = _row(id=uuid.uuid4(), author_id=OTHER_AUTHOR)
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=OTHER_AUTHOR))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)

    def test_reassign_to_inactive_author_conflicts(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot(id=OTHER_AUTHOR, is_active=False)
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=OTHER_AUTHOR))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_INACTIVE)

    def test_reassign_to_missing_author(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=OTHER_AUTHOR))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)

    def test_same_author_id_skips_reassign_checks(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.update.return_value = _row()
        self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_id=AUTHOR_ID, score=4))
        self.repo.get_author.assert_not_called()

    def test_updates_author_name_keeping_current_author(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.get_author.return_value = _snapshot()
        self.repo.update.return_value = _row(author_name='Ana Gómez')
        self.uc.execute(ROW_ID, UpdateTestimonialSchema(author_name='Ana Gómez'))
        payload = self.repo.update.call_args.args[1]
        self.assertEqual(payload.author_name, 'Ana Gómez')

    def test_quote_change_clears_signature(self):
        self.repo.get_by_id.return_value = _row(
            seal='b' * 64,
            content_hash='a' * 64,
            signed_at=datetime.now(timezone.utc),
        )
        self.repo.update.return_value = _row(score=4, seal='')
        self.uc.execute(ROW_ID, UpdateTestimonialSchema(score=4))
        payload = self.repo.update.call_args.args[1]
        self.assertEqual(payload.seal, '')
        self.assertIsNone(payload.signed_at)

    def test_raises_if_row_vanishes_during_update(self):
        self.repo.get_by_id.return_value = _row()
        self.repo.update.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(ROW_ID, UpdateTestimonialSchema(score=2))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_NOT_FOUND)
