"""Unit tests del encabezado From (core.email.domain.headers)."""

import pytest

from core.email.domain.headers import format_from_header, parse_from_address

pytestmark = pytest.mark.unit


class TestFormatFromHeader:

    def test_empty_returns_empty(self):
        assert format_from_header() == ''

    def test_bare_email(self):
        assert format_from_header('noreply@base.local') == 'noreply@base.local'

    def test_name_and_email(self):
        assert format_from_header('noreply@base.local', 'Base') == 'Base <noreply@base.local>'

    def test_already_formatted_is_kept(self):
        raw = 'Base <noreply@base.local>'
        assert format_from_header(raw, 'Ignored') == raw

    def test_falls_back_to_default_email(self):
        assert format_from_header(
            '', '', default_email='Base <noreply@base.local>',
        ) == 'Base <noreply@base.local>'

    def test_default_name_only_on_bare_email(self):
        assert format_from_header(
            'noreply@base.local', '', default_name='Base',
        ) == 'Base <noreply@base.local>'

    def test_explicit_name_wins_over_default_name(self):
        assert format_from_header(
            'noreply@base.local', 'Billing', default_name='Base',
        ) == 'Billing <noreply@base.local>'


class TestParseFromAddress:

    def test_empty(self):
        assert parse_from_address('') == ''

    def test_bare_email(self):
        assert parse_from_address('notificaciones@base.local') == 'notificaciones@base.local'

    def test_rfc5322_display_name(self):
        assert parse_from_address(
            'Notificaciones de la base <notificaciones@base.local>',
        ) == 'notificaciones@base.local'

    def test_strips_whitespace(self):
        assert parse_from_address('  ops@base.local  ') == 'ops@base.local'
