"""Unit tests for testimonial Django repositories (mocked ORM)."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from core.errors import ConflictException, NotFoundException
from core.errors.codes import AppErrorCode
from platform.features.configuration.landing.testimonial.domain.schemas import (
    CreateTestimonialSchema,
    SignedTestimonialDraft,
    TestimonialListFilters,
    TestimonialPromptReceiptSchema,
    UpdateTestimonialSchema,
)
from platform.features.configuration.landing.testimonial.infrastructure import repositories as repo_mod
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialPromptReceiptRepository,
    DjangoTestimonialRepository,
)

pytestmark = pytest.mark.unit


@contextmanager
def _noop_atomic():
    yield


@pytest.fixture(autouse=True)
def _skip_real_transactions():
    with patch.object(repo_mod.transaction, 'atomic', _noop_atomic):
        yield

AUTHOR_ID = uuid.uuid4()
ROW_ID = uuid.uuid4()
NEW_ID = uuid.uuid4()


def _orm(**overrides):
    obj = MagicMock()
    values = dict(
        id=ROW_ID,
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        author_name='María Restrepo',
        author_role='Ops',
        company_name='Andina',
        locale='es',
        is_published=True,
        sort_order=0,
        content_hash='a' * 64,
        seal='b' * 64,
        seal_algorithm='hmac-sha256-v1',
        canonical_payload='{}',
        signed_at=datetime.now(timezone.utc),
        signatory_id=str(AUTHOR_ID),
        tenant_id='',
        ip_address='',
        user_agent='',
        request_id='',
        channel='web',
        revoked_at=None,
        superseded_by_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    for key, value in values.items():
        setattr(obj, key, value)
    return obj


def _draft() -> SignedTestimonialDraft:
    return SignedTestimonialDraft(
        id=NEW_ID,
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        author_name='María Restrepo',
        locale='es',
        content_hash='c' * 64,
        seal='d' * 64,
        seal_algorithm='hmac-sha256-v1',
        canonical_payload='{"score":5}',
        signed_at=datetime.now(timezone.utc),
        signatory_id=str(AUTHOR_ID),
    )


class TestListPage(TestCase):

    def test_counts_then_slices(self):
        qs = MagicMock()
        qs.order_by.return_value = qs
        qs.filter.return_value = qs
        qs.count.return_value = 5
        qs.__getitem__ = MagicMock(return_value=[_orm(), _orm(id=uuid.uuid4())])
        repo = DjangoTestimonialRepository()
        with patch.object(repo, '_qs', return_value=qs):
            items, total = repo.list_page(
                TestimonialListFilters(locale='es'), offset=0, limit=2,
            )
        self.assertEqual(total, 5)
        self.assertEqual(len(items), 2)
        qs.filter.assert_called()


class TestReplaceLive(TestCase):

    def test_revokes_previous_and_links_successor(self):
        live = _orm()
        created = _orm(id=NEW_ID, seal='d' * 64)
        qs = MagicMock()
        qs.select_for_update.return_value.filter.return_value.first.return_value = live
        repo = DjangoTestimonialRepository()
        with patch.object(repo, '_qs', return_value=qs), patch.object(
            repo_mod, '_lock_author',
        ), patch.object(
            repo_mod.Testimonial.objects, 'create', return_value=created,
        ) as create:
            result = repo.replace_live(AUTHOR_ID, _draft())
        create.assert_called_once()
        self.assertEqual(result.id, NEW_ID)
        self.assertIsNotNone(live.revoked_at)
        self.assertEqual(live.superseded_by_id, NEW_ID)
        self.assertEqual(live.save.call_count, 2)

    def test_creates_when_no_live_row(self):
        created = _orm(id=NEW_ID)
        qs = MagicMock()
        qs.select_for_update.return_value.filter.return_value.first.return_value = None
        repo = DjangoTestimonialRepository()
        with patch.object(repo, '_qs', return_value=qs), patch.object(
            repo_mod, '_lock_author',
        ), patch.object(
            repo_mod.Testimonial.objects, 'create', return_value=created,
        ):
            result = repo.replace_live(AUTHOR_ID, _draft())
        self.assertEqual(result.id, NEW_ID)

    def test_duplicate_live_author_maps_conflict(self):
        qs = MagicMock()
        qs.select_for_update.return_value.filter.return_value.first.return_value = None
        repo = DjangoTestimonialRepository()
        with patch.object(repo, '_qs', return_value=qs), patch.object(
            repo_mod, '_lock_author',
        ), patch.object(
            repo_mod.Testimonial.objects, 'create',
            side_effect=IntegrityError('uniq_tst_live_author'),
        ):
            with self.assertRaises(ConflictException) as ctx:
                repo.replace_live(AUTHOR_ID, _draft())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)

    def test_missing_author_lock_is_not_found(self):
        with patch.object(
            repo_mod, '_lock_author',
            side_effect=NotFoundException(AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND),
        ):
            with self.assertRaises(NotFoundException) as ctx:
                DjangoTestimonialRepository().replace_live(AUTHOR_ID, _draft())
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)


class TestCreateMapsIntegrityError(TestCase):

    def test_unique_live_author(self):
        repo = DjangoTestimonialRepository()
        with patch.object(repo_mod, '_lock_author'), patch.object(
            repo_mod.Testimonial.objects, 'create',
            side_effect=IntegrityError('uniq_tst_live_author'),
        ):
            with self.assertRaises(ConflictException) as ctx:
                repo.create(CreateTestimonialSchema(
                    author_id=AUTHOR_ID,
                    score=5,
                    message='El picking guiado cambió la operación.',
                ))
        self.assertEqual(ctx.exception.code, AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)


class TestUpdateLocksLiveRow(TestCase):

    def test_missing_live_row_returns_none(self):
        qs = MagicMock()
        qs.select_for_update.return_value.get.side_effect = (
            repo_mod.Testimonial.DoesNotExist
        )
        repo = DjangoTestimonialRepository()
        with patch.object(repo, '_qs', return_value=qs):
            result = repo.update(ROW_ID, UpdateTestimonialSchema(score=4))
        self.assertIsNone(result)


class TestMarkPendingReprompt(TestCase):

    def test_bulk_updates_and_creates(self):
        existing_id = uuid.uuid4()
        missing_id = uuid.uuid4()
        existing = MagicMock(user_id=existing_id, pending_reprompt=False)
        qs = MagicMock()
        qs.filter.return_value = [existing]
        repo = DjangoTestimonialPromptReceiptRepository()
        with patch.object(
            repo_mod.TestimonialPromptReceipt.objects, 'select_for_update',
            return_value=qs,
        ), patch.object(
            repo_mod.TestimonialPromptReceipt.objects, 'bulk_update',
        ) as bulk_update, patch.object(
            repo_mod.TestimonialPromptReceipt.objects, 'bulk_create',
        ) as bulk_create:
            count = repo.mark_pending_reprompt([existing_id, missing_id])
        self.assertEqual(count, 2)
        bulk_update.assert_called_once()
        bulk_create.assert_called_once()
        created = bulk_create.call_args.args[0]
        self.assertEqual(len(created), 1)
