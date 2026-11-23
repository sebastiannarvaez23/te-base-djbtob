"""Unit tests for core.validators RequestBody / Field."""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

import pytest

from core.validators import Field, RequestBody, ValidationCode, validated_body
from django.utils.timezone import is_aware
from necore.query.patterns import PATTERN_TEXT


pytestmark = pytest.mark.unit


class LineBody(RequestBody):
    reference_id = Field(str, is_uuid=True)
    qty = Field(Decimal, min_value=0.000001)


class NestedParentBody(RequestBody):
    name = Field(str, max_length=40, pattern=PATTERN_TEXT)
    lines = Field(list, item=LineBody, min_items=1)


class AddressBody(RequestBody):
    city = Field(str, max_length=100, min_length=1, pattern=PATTERN_TEXT)
    zip_code = Field(str, max_length=32, pattern=PATTERN_TEXT, required=False, default='')


class WithSchemaBody(RequestBody):
    address = Field(dict, schema=AddressBody)


class ChoicesBody(RequestBody):
    # Explicit max_length so invalid choices are not rejected as MAX_LENGTH first.
    status = Field(str, max_length=32, choices=['draft', 'open'])
    priority = Field(int, required=False, choices=[1, 2, 3], default=1)


class DefaultsBody(RequestBody):
    title = Field(str, max_length=20, pattern=PATTERN_TEXT)
    notes = Field(str, max_length=500, pattern=PATTERN_TEXT, required=False, default='')
    active = Field(bool, required=False, default=True)


class DatesBody(RequestBody):
    day = Field(date)
    occurred_at = Field(datetime)


class TestFieldBasics(TestCase):
    def test_required_missing(self):
        body = DefaultsBody({})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.REQUIRED)

    def test_defaults_applied(self):
        body = DefaultsBody({'title': 'Hello'})
        ok, errors = body.validate()
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(body.validated_data['notes'], '')
        self.assertTrue(body.validated_data['active'])
        self.assertEqual(body.validated_data['title'], 'Hello')

    def test_choices_valid(self):
        body = ChoicesBody({'status': 'draft'})
        ok, _ = body.validate()
        self.assertTrue(ok)
        self.assertEqual(body.validated_data['priority'], 1)

    def test_choices_invalid(self):
        body = ChoicesBody({'status': 'closed'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_decimal_from_int_float_str(self):
        for raw in (5, 5.5, '5.5'):
            body = LineBody({
                'reference_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                'qty': raw,
            })
            ok, errors = body.validate()
            self.assertTrue(ok, msg=errors)
            self.assertIsInstance(body.validated_data['qty'], Decimal)
            self.assertIsInstance(body.validated_data['reference_id'], UUID)

    def test_uuid_invalid(self):
        body = LineBody({
            'reference_id': 'not-a-uuid',
            'qty': 1,
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_UUID)

    def test_decimal_min_value(self):
        body = LineBody({
            'reference_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            'qty': 0,
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.MIN_VALUE)

    def test_nested_list_ok(self):
        body = NestedParentBody({
            'name': 'R-1',
            'lines': [{
                'reference_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                'qty': '1.5',
            }],
        })
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        line = body.validated_data['lines'][0]
        self.assertEqual(line['qty'], Decimal('1.5'))

    def test_nested_list_prefixed_errors(self):
        body = NestedParentBody({
            'name': 'R-1',
            'lines': [{'reference_id': 'not-a-uuid', 'qty': 1}],
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'lines[0].reference_id')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_UUID)

    def test_min_items(self):
        body = NestedParentBody({'name': 'R-1', 'lines': []})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.MIN_ITEMS)

    def test_schema_nested_dict(self):
        body = WithSchemaBody({'address': {'city': 'Bogota'}})
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(body.validated_data['address']['city'], 'Bogota')
        self.assertEqual(body.validated_data['address']['zip_code'], '')

    def test_schema_nested_error_prefix(self):
        body = WithSchemaBody({'address': {}})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'address.city')

    def test_raw_data_preserved(self):
        payload = {'title': 'X'}
        body = DefaultsBody(payload)
        body.validate()
        self.assertEqual(body.data, payload)

    def test_unknown_field_rejected(self):
        body = DefaultsBody({'title': 'Hello', 'unexpected': True})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'unexpected')
        self.assertEqual(errors[0].code, ValidationCode.UNKNOWN_FIELD)

    def test_date_and_datetime_are_coerced_from_iso_json_strings(self):
        body = DatesBody({
            'day': '2024-03-15',
            'occurred_at': '2024-03-15T12:30:00',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(body.validated_data['day'], date(2024, 3, 15))
        self.assertEqual(
            body.validated_data['occurred_at'].replace(tzinfo=None),
            datetime(2024, 3, 15, 12, 30),
        )
        self.assertTrue(is_aware(body.validated_data['occurred_at']))
        self.assertEqual(body.validated_data['occurred_at'].tzinfo, dt_timezone.utc)

    def test_datetime_zulu_is_stored_as_utc_instant(self):
        body = DatesBody({
            'day': '2024-03-15',
            'occurred_at': '2024-03-15T12:30:00Z',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(
            body.validated_data['occurred_at'],
            datetime(2024, 3, 15, 12, 30, tzinfo=dt_timezone.utc),
        )

    def test_datetime_offset_is_stored_as_utc_instant(self):
        body = DatesBody({
            'day': '2024-03-15',
            'occurred_at': '2024-03-15T12:30:00-05:00',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(
            body.validated_data['occurred_at'],
            datetime(2024, 3, 15, 17, 30, tzinfo=dt_timezone.utc),
        )

    def test_invalid_calendar_date_is_validation_error(self):
        body = DatesBody({
            'day': '2024-13-40',
            'occurred_at': '2024-03-15T12:30:00Z',
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'day')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_date_rejects_datetime_and_datetime_rejects_date_only(self):
        body = DatesBody({
            'day': '2024-03-15T12:30:00Z',
            'occurred_at': '2024-03-15',
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual({error.field for error in errors}, {'day', 'occurred_at'})


class NameBody(RequestBody):
    name = Field(str, max_length=40, pattern=PATTERN_TEXT)


class TestValidatedBodyDecorator(TestCase):
    def test_injects_validated_body_and_preserves_route_kwargs(self):
        class View:
            @validated_body(NameBody)
            def post(self, request, resource_id, *, body: dict):
                return {
                    'resource_id': resource_id,
                    'name': body['name'],
                }

        result = View().post(
            SimpleNamespace(data={'name': 'pallet'}),
            resource_id='resource-1',
        )
        self.assertEqual(result, {'resource_id': 'resource-1', 'name': 'pallet'})

    def test_returns_validation_response_without_calling_view(self):
        called = False

        class View:
            @validated_body(NameBody)
            def post(self, request, *, body: dict):
                nonlocal called
                called = True
                return body

        response = View().post(SimpleNamespace(data={}))
        self.assertFalse(called)
        self.assertEqual(response.status_code, 400)

    def test_resolves_body_class_from_instance_attribute(self):
        class View:
            body_class = NameBody

            @validated_body('body_class')
            def post(self, request, *, body: dict):
                return body['name']

        self.assertEqual(
            View().post(SimpleNamespace(data={'name': 'bin'})),
            'bin',
        )

    def test_rejects_reserved_route_kwarg_name(self):
        class View:
            @validated_body(NameBody)
            def post(self, request, *, body: dict):
                return body

        with self.assertRaises(TypeError):
            View().post(SimpleNamespace(data={'name': 'x'}), body='route-kwarg')


class RecipientsBody(RequestBody):
    to = Field(list, min_items=1, max_items=50, item=str, is_email=True, max_length=254)


class TestPrimitiveListItems(TestCase):
    def test_email_list_valid(self):
        body = RecipientsBody({'to': ['ops@base.local']})
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(body.validated_data['to'], ['ops@base.local'])

    def test_email_list_invalid(self):
        body = RecipientsBody({'to': ['not-an-email']})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'to[0]')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_EMAIL)

    def test_email_list_item_wrong_type(self):
        body = RecipientsBody({'to': [1]})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_nested_request_body_lists_still_work(self):
        body = NestedParentBody({
            'name': 'R-1',
            'lines': [{
                'reference_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                'qty': '1.5',
            }],
        })
        ok, errors = body.validate()
        self.assertTrue(ok, msg=errors)
