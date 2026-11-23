from datetime import datetime, timezone, timedelta
from unittest import TestCase

import pytest

from core.instants import InstantError, ensure_utc, jsonable, parse_instant, serialize_instant

pytestmark = pytest.mark.unit

UTC = timezone.utc


class TestParseInstant(TestCase):

    def test_empty_is_none(self):
        self.assertIsNone(parse_instant(None))
        self.assertIsNone(parse_instant(''))
        self.assertIsNone(parse_instant('   '))

    def test_zulu_is_utc(self):
        parsed = parse_instant('2026-01-15T19:00:00Z')
        self.assertEqual(parsed, datetime(2026, 1, 15, 19, 0, tzinfo=UTC))

    def test_offset_converts_to_utc(self):
        parsed = parse_instant('2026-01-15T14:00:00-05:00')
        self.assertEqual(parsed, datetime(2026, 1, 15, 19, 0, tzinfo=UTC))

    def test_naive_iso_is_assumed_utc(self):
        parsed = parse_instant('2026-01-15T19:00:00')
        self.assertEqual(parsed, datetime(2026, 1, 15, 19, 0, tzinfo=UTC))
        self.assertEqual(parsed.tzinfo, UTC)

    def test_space_separated_iso_is_accepted(self):
        parsed = parse_instant('2026-01-15 14:00')
        self.assertEqual(parsed, datetime(2026, 1, 15, 14, 0, tzinfo=UTC))

    def test_aware_datetime_normalizes_to_utc(self):
        bogota = timezone(timedelta(hours=-5))
        parsed = parse_instant(datetime(2026, 1, 15, 14, 0, tzinfo=bogota))
        self.assertEqual(parsed, datetime(2026, 1, 15, 19, 0, tzinfo=UTC))

    def test_date_only_is_rejected(self):
        with self.assertRaises(InstantError):
            parse_instant('2026-01-15')

    def test_garbage_is_rejected(self):
        with self.assertRaises(InstantError):
            parse_instant('not-a-date')
        with self.assertRaises(InstantError):
            parse_instant(15)


class TestSerializeInstant(TestCase):

    def test_utc_uses_z_suffix(self):
        self.assertEqual(
            serialize_instant(datetime(2026, 1, 15, 19, 0, tzinfo=UTC)),
            '2026-01-15T19:00:00Z',
        )

    def test_offset_is_folded_to_z(self):
        bogota = timezone(timedelta(hours=-5))
        self.assertEqual(
            serialize_instant(datetime(2026, 1, 15, 14, 0, tzinfo=bogota)),
            '2026-01-15T19:00:00Z',
        )

    def test_naive_is_assumed_utc(self):
        self.assertEqual(
            serialize_instant(datetime(2026, 1, 15, 19, 0)),
            '2026-01-15T19:00:00Z',
        )


class TestJsonable(TestCase):

    def test_datetime_and_offset_strings_use_z(self):
        payload = jsonable({
            'at': datetime(2026, 1, 15, 19, 0, tzinfo=UTC),
            'nested': {'iso': '2026-01-15T19:00:00+00:00'},
            'items': ['2026-01-15T19:00:00.123456+00:00'],
            'note': '2026-01-15T19:00:00+00:00 extra',
        })
        self.assertEqual(payload['at'], '2026-01-15T19:00:00Z')
        self.assertEqual(payload['nested']['iso'], '2026-01-15T19:00:00Z')
        self.assertEqual(payload['items'][0], '2026-01-15T19:00:00.123456Z')
        self.assertEqual(payload['note'], '2026-01-15T19:00:00+00:00 extra')


class TestEnsureUtc(TestCase):

    def test_naive_gets_utc_tzinfo(self):
        dt = ensure_utc(datetime(2026, 9, 13, 12, 0))
        self.assertEqual(dt.tzinfo, UTC)
        self.assertEqual(dt.hour, 12)
