"""Unit tests for testimonial RequestBody / QueryFilter contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.query import PaginatedQuery
from platform.features.configuration.landing.testimonial.domain.schemas import (
    PublicTestimonialSchema,
    TestimonialListFilters,
)
from platform.features.configuration.landing.testimonial.presentation.bodies import (
    CreateTestimonialBody,
    SubmitMyTestimonialBody,
    UpdateTestimonialBody,
)
from platform.features.configuration.landing.testimonial.presentation.catalog import catalog_response
from platform.features.configuration.landing.testimonial.presentation.queries import (
    PublicTestimonialListQuery,
    TestimonialListQuery,
)

pytestmark = pytest.mark.unit


def _create_payload(**overrides) -> dict:
    data = {
        'author_id': str(uuid4()),
        'score': 5,
        'message': 'Implementarlo fue rápido.',
    }
    data.update(overrides)
    return data


class TestCreateTestimonialBody:

    def test_accepts_minimal_payload(self):
        ok, errors = CreateTestimonialBody(_create_payload()).validate()
        assert ok is True
        assert errors == []

    def test_rejects_score_out_of_range(self):
        ok, errors = CreateTestimonialBody(_create_payload(score=0)).validate()
        assert ok is False
        assert any(e.field == 'score' for e in errors)

    def test_rejects_invalid_author_id(self):
        ok, errors = CreateTestimonialBody(_create_payload(author_id='not-a-uuid')).validate()
        assert ok is False
        assert any(e.field == 'author_id' for e in errors)

    def test_rejects_unknown_locale(self):
        ok, errors = CreateTestimonialBody(_create_payload(locale='fr')).validate()
        assert ok is False
        assert any(e.field == 'locale' for e in errors)

    def test_rejects_unknown_field(self):
        ok, errors = CreateTestimonialBody(
            _create_payload(extra='nope'),
        ).validate()
        assert ok is False

    def test_rejects_message_too_long(self):
        ok, errors = CreateTestimonialBody(
            _create_payload(message='x' * 2001),
        ).validate()
        assert ok is False
        assert any(e.field == 'message' for e in errors)


class TestSubmitMyTestimonialBody:

    def test_accepts_score_and_message(self):
        ok, errors = SubmitMyTestimonialBody({
            'score': 5,
            'message': 'El picking guiado nos ahorró tiempo.',
            'accepted': True,
        }).validate()
        assert ok is True
        assert errors == []

    def test_rejects_unsigned(self):
        ok, errors = SubmitMyTestimonialBody({
            'score': 5,
            'message': 'El picking guiado nos ahorró tiempo.',
            'accepted': False,
        }).validate()
        assert ok is False
        assert any(e.field == 'accepted' for e in errors)

    def test_rejects_missing_accepted(self):
        ok, errors = SubmitMyTestimonialBody({
            'score': 5,
            'message': 'El picking guiado nos ahorró tiempo.',
        }).validate()
        assert ok is False
        assert any(e.field == 'accepted' for e in errors)

    def test_rejects_short_message(self):
        ok, errors = SubmitMyTestimonialBody({
            'score': 4,
            'message': 'corto',
            'accepted': True,
        }).validate()
        assert ok is False
        assert any(e.field == 'message' for e in errors)

    def test_rejects_author_id_from_client(self):
        ok, errors = SubmitMyTestimonialBody({
            'score': 5,
            'message': 'El picking guiado nos ahorró tiempo.',
            'accepted': True,
            'author_id': str(uuid4()),
        }).validate()
        assert ok is False


class TestUpdateTestimonialBody:

    def test_allows_partial_patch(self):
        ok, errors = UpdateTestimonialBody({'is_published': True}).validate()
        assert ok is True
        assert errors == []

    def test_rejects_score_above_five(self):
        ok, errors = UpdateTestimonialBody({'score': 9}).validate()
        assert ok is False
        assert any(e.field == 'score' for e in errors)


class TestTestimonialListQuery:

    def test_parses_filters(self):
        query, err = TestimonialListQuery({
            'score': '5',
            'locale': 'es',
            'is_published': 'true',
        }).parse()
        assert err is None
        assert query.filters['score'] == 5
        assert query.filters['locale'] == 'es'
        assert query.filters['is_published'] is True

    def test_rejects_invalid_score(self):
        query, err = TestimonialListQuery({'score': '9'}).parse()
        assert query is None
        assert err is not None


class TestPublicTestimonialListQuery:

    def test_locale_only(self):
        query, err = PublicTestimonialListQuery({'locale': 'en'}).parse()
        assert err is None
        assert query.filters == {'locale': 'en'}
        assert query.unpaginated is True

    def test_rejects_invalid_locale(self):
        query, err = PublicTestimonialListQuery({'locale': 'fr'}).parse()
        assert query is None
        assert err is not None


class TestTestimonialListFilters:

    def test_from_query_keeps_known_keys(self):
        author_id = uuid4()
        filters = TestimonialListFilters.from_query({
            'locale': 'EN',
            'author_id': str(author_id),
            'extra': 'drop-me',
        })
        assert filters.locale == 'en'
        assert filters.author_id == author_id
        assert filters.signed is None


class TestCatalogResponse:

    def _item(self) -> PublicTestimonialSchema:
        return PublicTestimonialSchema(
            id=uuid4(),
            score=5,
            message='El picking guiado cambió la operación.',
            author_name='María Restrepo',
            locale='es',
            signed_at=datetime.now(timezone.utc),
            seal_fingerprint='abcd1234',
        )

    def test_unpaginated_returns_full_list(self):
        items = [self._item(), self._item()]
        query = PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)
        response = catalog_response(query, items)
        assert response.status_code == 200
        assert len(response.data['data']) == 2

    def test_paginated_slices_and_counts(self):
        items = [self._item() for _ in range(3)]
        query = PaginatedQuery(page=1, page_size=2, filters={}, unpaginated=False)
        response = catalog_response(query, items)
        payload = response.data['data']
        assert payload['total'] == 3
        assert payload['page'] == 1
        assert payload['page_size'] == 2
        assert payload['total_pages'] == 2
        assert len(payload['items']) == 1

    def test_paginated_uses_sql_total_when_provided(self):
        items = [self._item()]
        query = PaginatedQuery(page=1, page_size=2, filters={}, unpaginated=False)
        response = catalog_response(query, items, total=3)
        payload = response.data['data']
        assert payload['total'] == 3
        assert payload['total_pages'] == 2
        assert len(payload['items']) == 1
