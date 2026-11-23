"""Unit tests for core.logging_redaction.

Redacción compartida por el middleware de request/response y el buffer de
transacciones. Estas pruebas fijan el contrato: los secretos nunca salen en
claro, el JSON se compacta a una línea y los payloads gigantes se truncan.
"""
import json
from unittest import TestCase

from core.logging_redaction import (
    MAX_BODY_CHARS,
    TRUNCATED_MARK,
    inline_json,
    mask_secrets,
)


class MaskSecretsTests(TestCase):

    def test_masks_top_level_sensitive_keys(self):
        masked = mask_secrets({'username': 'ana', 'password': 's3cr3t'})
        self.assertEqual(masked, {'username': 'ana', 'password': '***'})

    def test_masks_nested_keys_in_dicts_and_lists(self):
        data = {
            'user': 'ana',
            'auth': {'token': 'abc', 'refresh': 'xyz'},
            'items': [{'api_key': 'k1'}, {'name': 'ok'}],
        }
        masked = mask_secrets(data)
        self.assertEqual(masked['auth'], {'token': '***', 'refresh': '***'})
        self.assertEqual(masked['items'][0], {'api_key': '***'})
        self.assertEqual(masked['items'][1], {'name': 'ok'})

    def test_key_match_is_case_insensitive(self):
        self.assertEqual(mask_secrets({'Password': 'x'}), {'Password': '***'})

    def test_masks_otp_and_challenge_id(self):
        masked = mask_secrets({'challenge_id': 'abc', 'otp_code': '123456', 'user': 'ana'})
        self.assertEqual(masked['challenge_id'], '***')
        self.assertEqual(masked['otp_code'], '***')
        self.assertEqual(masked['user'], 'ana')

    def test_scalars_pass_through(self):
        self.assertEqual(mask_secrets('plain'), 'plain')
        self.assertEqual(mask_secrets(42), 42)

    def test_does_not_mutate_input(self):
        original = {'password': 'x'}
        mask_secrets(original)
        self.assertEqual(original, {'password': 'x'})


class InlineJsonTests(TestCase):

    def test_empty_returns_dash(self):
        self.assertEqual(inline_json(''), '-')
        self.assertEqual(inline_json(None), '-')

    def test_valid_json_is_compacted_and_masked(self):
        out = inline_json('{"username": "ana", "password": "s3cr3t"}')
        self.assertEqual(out, '{"username":"ana","password":"***"}')

    def test_compact_removes_whitespace(self):
        out = inline_json('{ "a":  1,\n  "b":   2 }')
        self.assertEqual(out, '{"a":1,"b":2}')

    def test_non_json_collapses_whitespace(self):
        self.assertEqual(inline_json('texto   no\njson'), 'texto no json')

    def test_truncates_oversized_payload(self):
        big = json.dumps({'blob': 'x' * (MAX_BODY_CHARS * 2)})
        out = inline_json(big)
        self.assertTrue(out.endswith(TRUNCATED_MARK))
        self.assertLessEqual(len(out), MAX_BODY_CHARS + len(TRUNCATED_MARK))

    def test_unicode_preserved(self):
        self.assertEqual(inline_json('{"city": "Bogotá"}'), '{"city":"Bogotá"}')
