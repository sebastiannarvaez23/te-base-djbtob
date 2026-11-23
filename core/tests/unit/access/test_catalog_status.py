"""Unit tests for catalog access diagnose (MOD_004 / SEC_003 / FUNC_003)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.access.catalog_status import check_module_code, check_section_code, diagnose_feature_key
from core.access.result import AccessResult
from core.errors import AppErrorCode


@pytest.mark.unit
class TestDiagnoseFeatureKey:
    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_section_inactive(self, MockFunc):
        section = SimpleNamespace(code='WMS', is_active=False)
        module = SimpleNamespace(code='ORDERS', is_active=True, section=section)
        row = SimpleNamespace(key='orders.create', is_active=True, module=module)
        MockFunc.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = row

        result = diagnose_feature_key('orders.create')
        assert result is not None
        assert result.error_code == AppErrorCode.SECTION_INACTIVE

    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_module_inactive(self, MockFunc):
        section = SimpleNamespace(code='WMS', is_active=True)
        module = SimpleNamespace(code='ORDERS', is_active=False, section=section)
        row = SimpleNamespace(key='orders.create', is_active=True, module=module)
        MockFunc.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = row

        result = diagnose_feature_key('orders.create')
        assert result is not None
        assert result.error_code == AppErrorCode.MODULE_INACTIVE

    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_functionality_inactive(self, MockFunc):
        section = SimpleNamespace(code='WMS', is_active=True)
        module = SimpleNamespace(code='ORDERS', is_active=True, section=section)
        row = SimpleNamespace(key='orders.create', is_active=False, module=module)
        MockFunc.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = row

        result = diagnose_feature_key('orders.create')
        assert result is not None
        assert result.error_code == AppErrorCode.FUNC_INACTIVE

    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_active_returns_none(self, MockFunc):
        section = SimpleNamespace(code='WMS', is_active=True)
        module = SimpleNamespace(code='ORDERS', is_active=True, section=section)
        row = SimpleNamespace(key='orders.create', is_active=True, module=module)
        MockFunc.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = row

        assert diagnose_feature_key('orders.create') is None

    @patch('platform.features.security.access.functionalities.models.Functionality')
    def test_database_error_is_not_rewritten(self, MockFunc):
        MockFunc.objects.filter.side_effect = RuntimeError('db down')
        with pytest.raises(RuntimeError, match='db down'):
            diagnose_feature_key('orders.create')


@pytest.mark.unit
class TestCheckModuleCode:
    @patch('platform.features.security.access.modules.models.Module')
    def test_inactive_module(self, MockModule):
        section = SimpleNamespace(code='WMS', is_active=True)
        module = SimpleNamespace(code='ORDERS', is_active=False, section=section)
        MockModule.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = module

        result = check_module_code('ORDERS')
        assert result.error_code == AppErrorCode.MODULE_INACTIVE

    @patch('platform.features.security.access.modules.models.Module')
    def test_inactive_section_wins(self, MockModule):
        section = SimpleNamespace(code='WMS', is_active=False)
        module = SimpleNamespace(code='ORDERS', is_active=True, section=section)
        MockModule.objects.filter.return_value.select_related.return_value.only.return_value.first.return_value = module

        result = check_module_code('ORDERS')
        assert result.error_code == AppErrorCode.SECTION_INACTIVE


@pytest.mark.unit
class TestCheckSectionCode:
    @patch('platform.features.security.access.sections.models.Section')
    def test_inactive(self, MockSection):
        MockSection.objects.filter.return_value.only.return_value.first.return_value = SimpleNamespace(
            code='WMS', is_active=False,
        )
        result = check_section_code('WMS')
        assert result.error_code == AppErrorCode.SECTION_INACTIVE


@pytest.mark.unit
class TestAccessResultConstructors:
    def test_module_inactive(self):
        r = AccessResult.module_inactive(module_code='ORDERS')
        assert r.error_code == AppErrorCode.MODULE_INACTIVE
        assert r.context['module_code'] == 'ORDERS'

    def test_functionality_inactive(self):
        r = AccessResult.functionality_inactive('orders.create')
        assert r.error_code == AppErrorCode.FUNC_INACTIVE
