"""Unit tests for core/admin_parameters.py facade."""
from unittest import TestCase
from unittest.mock import patch


class TestGetAdminParameter(TestCase):

    def _call(self, code, default=None):
        from core.admin_parameters import get_admin_parameter
        return get_admin_parameter(code, default=default)

    @patch('core.admin_parameters._cache')
    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter.models'
        '.AdminParameter.objects',
    )
    def test_returns_int_value(self, mock_objects, mock_cache):
        mock_cache.return_value.get.return_value = object()  # force miss via _MISS
        # Use real miss sentinel: return a unique object that equals _MISS check
        from core import admin_parameters as mod
        mock_cache.return_value.get.side_effect = lambda key, default=None: default
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '42', 'data_type': 'INT',
        }
        result = self._call('TOKEN_DURATION')
        self.assertEqual(result, 42)

    @patch('core.admin_parameters._cache')
    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter.models'
        '.AdminParameter.objects',
    )
    def test_returns_bool_true(self, mock_objects, mock_cache):
        mock_cache.return_value.get.side_effect = lambda key, default=None: default
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': 'true', 'data_type': 'BOOL',
        }
        self.assertTrue(self._call('DOUBLE_FA_AUTH'))

    @patch('core.admin_parameters._cache')
    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter.models'
        '.AdminParameter.objects',
    )
    def test_returns_default_when_missing(self, mock_objects, mock_cache):
        mock_cache.return_value.get.side_effect = lambda key, default=None: default
        mock_objects.filter.return_value.values.return_value.first.return_value = None
        self.assertEqual(self._call('MISSING', default=7), 7)

    @patch('core.admin_parameters._cache')
    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter.models'
        '.AdminParameter.objects',
    )
    def test_filters_active_only(self, mock_objects, mock_cache):
        mock_cache.return_value.get.side_effect = lambda key, default=None: default
        mock_objects.filter.return_value.values.return_value.first.return_value = None
        self._call('TOKEN_DURATION')
        mock_objects.filter.assert_called_once_with(code='TOKEN_DURATION', is_active=True)

    @patch('core.admin_parameters._cache')
    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter.models'
        '.AdminParameter.objects',
    )
    def test_does_not_touch_client_parameter_model(self, mock_objects, mock_cache):
        mock_cache.return_value.get.side_effect = lambda key, default=None: default
        mock_objects.filter.return_value.values.return_value.first.return_value = {
            'value': '14', 'data_type': 'INT',
        }
        with patch(
            'platform.features.configuration.parameters.parameter.models.Parameter.objects',
        ) as client_objects:
            self._call('REF_TOKEN_DURATION')
            client_objects.filter.assert_not_called()
            client_objects.get.assert_not_called()
