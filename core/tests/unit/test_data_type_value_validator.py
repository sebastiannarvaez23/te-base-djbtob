"""
Unit tests for core.validators.DataTypeValueValidator.

Covers:
- validate(): success (no exception) and failure (raises ValidationAppException)
- is_valid(): returns True/False mirror of validate()
- Error response: correct AppErrorCode, http_status, message, and detail
- Custom field_name in error detail
- Case-insensitive data_type handling
- All data types: STRING, INT, DECIMAL, BOOL, JSON
- Unknown data type handling
"""

from unittest import TestCase

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from core.validators.data_type import DataTypeValueValidator


class TestValidateString(TestCase):
    """STRING accepts any value — no casting restrictions."""

    def test_accepts_any_text(self):
        DataTypeValueValidator.validate('hello world', 'STRING')

    def test_accepts_empty_string(self):
        DataTypeValueValidator.validate('', 'STRING')

    def test_accepts_special_characters(self):
        DataTypeValueValidator.validate('!@#$%^&*()', 'STRING')

    def test_accepts_numeric_string(self):
        DataTypeValueValidator.validate('12345', 'STRING')

    def test_accepts_json_like_string(self):
        DataTypeValueValidator.validate('{"key": "value"}', 'STRING')

    def test_is_valid_returns_true(self):
        self.assertTrue(DataTypeValueValidator.is_valid('anything', 'STRING'))

    def test_is_valid_returns_true_for_empty(self):
        self.assertTrue(DataTypeValueValidator.is_valid('', 'STRING'))


class TestValidateInt(TestCase):
    """INT requires the value to be castable to int."""

    # ── Success ──────────────────────────────────────────────────────────
    def test_accepts_positive_integer(self):
        DataTypeValueValidator.validate('42', 'INT')

    def test_accepts_negative_integer(self):
        DataTypeValueValidator.validate('-7', 'INT')

    def test_accepts_zero(self):
        DataTypeValueValidator.validate('0', 'INT')

    def test_accepts_large_number(self):
        DataTypeValueValidator.validate('999999999', 'INT')

    def test_is_valid_returns_true(self):
        self.assertTrue(DataTypeValueValidator.is_valid('42', 'INT'))

    # ── Failure ──────────────────────────────────────────────────────────
    def test_rejects_float_string(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('3.14', 'INT')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)
        self.assertIn('not a valid integer', ctx.exception.detail)

    def test_rejects_text(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('abc', 'INT')

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'INT')

    def test_rejects_whitespace(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('   ', 'INT')

    def test_is_valid_returns_false(self):
        self.assertFalse(DataTypeValueValidator.is_valid('abc', 'INT'))

    def test_is_valid_returns_false_for_float(self):
        self.assertFalse(DataTypeValueValidator.is_valid('3.14', 'INT'))


class TestValidateDecimal(TestCase):
    """DECIMAL requires the value to be castable to float."""

    # ── Success ──────────────────────────────────────────────────────────
    def test_accepts_float(self):
        DataTypeValueValidator.validate('19.5', 'DECIMAL')

    def test_accepts_integer_string(self):
        DataTypeValueValidator.validate('100', 'DECIMAL')

    def test_accepts_negative_float(self):
        DataTypeValueValidator.validate('-0.5', 'DECIMAL')

    def test_accepts_zero(self):
        DataTypeValueValidator.validate('0', 'DECIMAL')

    def test_accepts_scientific_notation(self):
        DataTypeValueValidator.validate('1e10', 'DECIMAL')

    def test_is_valid_returns_true(self):
        self.assertTrue(DataTypeValueValidator.is_valid('3.14', 'DECIMAL'))

    # ── Failure ──────────────────────────────────────────────────────────
    def test_rejects_text(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('not-a-number', 'DECIMAL')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)
        self.assertIn('not a valid decimal', ctx.exception.detail)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'DECIMAL')

    def test_rejects_special_characters(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('$19.5', 'DECIMAL')

    def test_is_valid_returns_false(self):
        self.assertFalse(DataTypeValueValidator.is_valid('abc', 'DECIMAL'))


class TestValidateBool(TestCase):
    """BOOL accepts true/false, 1/0, yes/no (case-insensitive)."""

    # ── Success ──────────────────────────────────────────────────────────
    def test_accepts_true(self):
        DataTypeValueValidator.validate('true', 'BOOL')

    def test_accepts_false(self):
        DataTypeValueValidator.validate('false', 'BOOL')

    def test_accepts_1(self):
        DataTypeValueValidator.validate('1', 'BOOL')

    def test_accepts_0(self):
        DataTypeValueValidator.validate('0', 'BOOL')

    def test_accepts_yes(self):
        DataTypeValueValidator.validate('yes', 'BOOL')

    def test_accepts_no(self):
        DataTypeValueValidator.validate('no', 'BOOL')

    def test_accepts_uppercase_true(self):
        DataTypeValueValidator.validate('TRUE', 'BOOL')

    def test_accepts_mixed_case_false(self):
        DataTypeValueValidator.validate('False', 'BOOL')

    def test_accepts_uppercase_yes(self):
        DataTypeValueValidator.validate('YES', 'BOOL')

    def test_is_valid_returns_true(self):
        self.assertTrue(DataTypeValueValidator.is_valid('true', 'BOOL'))

    # ── Failure ──────────────────────────────────────────────────────────
    def test_rejects_arbitrary_text(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('maybe', 'BOOL')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)
        self.assertIn('not a valid boolean', ctx.exception.detail)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'BOOL')

    def test_rejects_numeric_other_than_0_1(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('2', 'BOOL')

    def test_rejects_si(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('si', 'BOOL')

    def test_is_valid_returns_false(self):
        self.assertFalse(DataTypeValueValidator.is_valid('maybe', 'BOOL'))


class TestValidateJson(TestCase):
    """JSON requires the value to be parseable by json.loads."""

    # ── Success ──────────────────────────────────────────────────────────
    def test_accepts_object(self):
        DataTypeValueValidator.validate('{"key": "value"}', 'JSON')

    def test_accepts_array(self):
        DataTypeValueValidator.validate('[1, 2, 3]', 'JSON')

    def test_accepts_string(self):
        DataTypeValueValidator.validate('"hello"', 'JSON')

    def test_accepts_number(self):
        DataTypeValueValidator.validate('42', 'JSON')

    def test_accepts_null(self):
        DataTypeValueValidator.validate('null', 'JSON')

    def test_accepts_boolean(self):
        DataTypeValueValidator.validate('true', 'JSON')

    def test_accepts_nested_object(self):
        DataTypeValueValidator.validate('{"a": {"b": [1, 2]}}', 'JSON')

    def test_is_valid_returns_true(self):
        self.assertTrue(DataTypeValueValidator.is_valid('{"k": 1}', 'JSON'))

    # ── Failure ──────────────────────────────────────────────────────────
    def test_rejects_invalid_json(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('{invalid}', 'JSON')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)
        self.assertIn('not valid JSON', ctx.exception.detail)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'JSON')

    def test_rejects_plain_text(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('hello', 'JSON')

    def test_rejects_trailing_comma(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('{"a": 1,}', 'JSON')

    def test_is_valid_returns_false(self):
        self.assertFalse(DataTypeValueValidator.is_valid('{bad}', 'JSON'))


class TestUnknownDataType(TestCase):
    """Unknown data types should raise ValidationAppException."""

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('value', 'UNKNOWN')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)
        self.assertIn("Unknown data type", ctx.exception.detail)

    def test_is_valid_returns_false_for_unknown_type(self):
        self.assertFalse(DataTypeValueValidator.is_valid('value', 'UNKNOWN'))


class TestCaseInsensitiveDataType(TestCase):
    """data_type parameter should be case-insensitive."""

    def test_accepts_lowercase_int(self):
        DataTypeValueValidator.validate('42', 'int')

    def test_accepts_mixed_case_bool(self):
        DataTypeValueValidator.validate('true', 'Bool')

    def test_accepts_lowercase_json(self):
        DataTypeValueValidator.validate('{}', 'json')

    def test_accepts_lowercase_decimal(self):
        DataTypeValueValidator.validate('3.14', 'decimal')

    def test_accepts_lowercase_string(self):
        DataTypeValueValidator.validate('hello', 'string')


class TestErrorResponse(TestCase):
    """Validate the structure of the raised exception."""

    def test_error_code_is_param_invalid_value(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'INT')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_http_status_is_400(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'INT')
        self.assertEqual(ctx.exception.http_status, 400)

    def test_message_matches_registry(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'INT')
        self.assertEqual(ctx.exception.message, 'Invalid parameter value')

    def test_detail_contains_value(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('xyz', 'INT')
        self.assertIn('xyz', ctx.exception.detail)

    def test_detail_contains_default_field_name(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'INT')
        self.assertIn("Field 'value'", ctx.exception.detail)

    def test_detail_contains_custom_field_name(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'INT', field_name='custom_field')
        self.assertIn("Field 'custom_field'", ctx.exception.detail)

    def test_detail_for_bool_includes_hint(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('maybe', 'BOOL')
        self.assertIn('true/false, 1/0, yes/no', ctx.exception.detail)

    def test_detail_for_json_mentions_json(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('{bad}', 'JSON')
        self.assertIn('not valid JSON', ctx.exception.detail)

    def test_detail_for_decimal_mentions_decimal(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('abc', 'DECIMAL')
        self.assertIn('not a valid decimal', ctx.exception.detail)

    def test_detail_for_unknown_type_includes_type_name(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('x', 'FOOBAR')
        self.assertIn('FOOBAR', ctx.exception.detail)


class TestIsValidMirrorsValidate(TestCase):
    """is_valid() should return True when validate() passes, False when it raises."""

    def test_valid_int(self):
        self.assertTrue(DataTypeValueValidator.is_valid('10', 'INT'))
        DataTypeValueValidator.validate('10', 'INT')  # no exception

    def test_invalid_int(self):
        self.assertFalse(DataTypeValueValidator.is_valid('abc', 'INT'))
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('abc', 'INT')

    def test_valid_bool(self):
        self.assertTrue(DataTypeValueValidator.is_valid('yes', 'BOOL'))
        DataTypeValueValidator.validate('yes', 'BOOL')

    def test_invalid_bool(self):
        self.assertFalse(DataTypeValueValidator.is_valid('maybe', 'BOOL'))
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('maybe', 'BOOL')

    def test_valid_json(self):
        self.assertTrue(DataTypeValueValidator.is_valid('[1]', 'JSON'))
        DataTypeValueValidator.validate('[1]', 'JSON')

    def test_invalid_json(self):
        self.assertFalse(DataTypeValueValidator.is_valid('{x}', 'JSON'))
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('{x}', 'JSON')

    def test_valid_decimal(self):
        self.assertTrue(DataTypeValueValidator.is_valid('3.14', 'DECIMAL'))
        DataTypeValueValidator.validate('3.14', 'DECIMAL')

    def test_invalid_decimal(self):
        self.assertFalse(DataTypeValueValidator.is_valid('abc', 'DECIMAL'))
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('abc', 'DECIMAL')
