"""
Unit tests for core/parameters.py facade (get_parameter).

Covers:
- Casting for each data type (STRING, INT, DECIMAL, BOOL, JSON)
- Default value when parameter not found
- Default value when parameter is inactive
- Graceful fallback on unexpected errors
"""
from unittest import TestCase
from unittest.mock import patch


class TestGetParameter(TestCase):

    def _call(self, code, default=None):
        from core.parameters import get_parameter
        return get_parameter(code, default=default)

    def setUp(self):
        cache_patch = patch('core.parameters._cache')
        self.mock_cache = cache_patch.start()
        self.addCleanup(cache_patch.stop)
        # Force cache miss on every read
        self.mock_cache.return_value.get.side_effect = lambda key, default=None: default

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_string_value(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'hello', 'data_type': 'STRING',
        }
        result = self._call('MY_PARAM')
        self.assertEqual(result, 'hello')
        self.assertIsInstance(result, str)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_int_value(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '42', 'data_type': 'INT',
        }
        result = self._call('MAX_RETRIES')
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_decimal_value(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '19.5', 'data_type': 'DECIMAL',
        }
        result = self._call('TAX_RATE')
        self.assertEqual(result, 19.5)
        self.assertIsInstance(result, float)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_bool_true(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'true', 'data_type': 'BOOL',
        }
        result = self._call('DOUBLE_FA_AUTH')
        self.assertTrue(result)
        self.assertIsInstance(result, bool)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_bool_false(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'false', 'data_type': 'BOOL',
        }
        result = self._call('DOUBLE_FA_AUTH')
        self.assertFalse(result)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_bool_true_for_1(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '1', 'data_type': 'BOOL',
        }
        self.assertTrue(self._call('FLAG'))

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_bool_false_for_0(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '0', 'data_type': 'BOOL',
        }
        self.assertFalse(self._call('FLAG'))

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_bool_true_for_yes(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'yes', 'data_type': 'BOOL',
        }
        self.assertTrue(self._call('FLAG'))

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_json_dict(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '{"host": "smtp.example.com", "port": 587}', 'data_type': 'JSON',
        }
        result = self._call('SMTP_CONFIG')
        self.assertEqual(result, {'host': 'smtp.example.com', 'port': 587})
        self.assertIsInstance(result, dict)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_json_array(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '[1, 2, 3]', 'data_type': 'JSON',
        }
        result = self._call('ALLOWED_IDS')
        self.assertEqual(result, [1, 2, 3])

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_default_when_not_found(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = None
        result = self._call('MISSING_PARAM', default='fallback')
        self.assertEqual(result, 'fallback')

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_none_default_when_not_found(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = None
        result = self._call('MISSING_PARAM')
        self.assertIsNone(result)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_returns_default_on_exception(self, mock_objects):
        mock_objects.filter.side_effect = Exception('DB error')
        result = self._call('ANY_PARAM', default=99)
        self.assertEqual(result, 99)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_filters_by_code_and_active(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'x', 'data_type': 'STRING',
        }
        self._call('MY_CODE')
        mock_objects.filter.assert_called_once_with(code='MY_CODE', is_active=True)

    @patch('platform.features.configuration.parameters.parameter.models.Parameter.objects')
    def test_unknown_data_type_falls_back_to_str(self, mock_objects):
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '123', 'data_type': 'UNKNOWN',
        }
        result = self._call('WEIRD_PARAM')
        self.assertEqual(result, '123')
        self.assertIsInstance(result, str)
