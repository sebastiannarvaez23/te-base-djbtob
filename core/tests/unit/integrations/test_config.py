"""Config factory y error codes."""

import pytest

from core.errors import AppErrorCode
from core.errors.codes import ERROR_REGISTRY
from core.integrations import ConnectorProvider, FakeConnector, get_connector, is_integrations_enabled

from .conftest import make_profile


@pytest.mark.unit
class TestConfig:

    def test_get_connector_fake(self):
        assert isinstance(get_connector(make_profile(ConnectorProvider.FAKE)), FakeConnector)

    def test_integrations_enabled_default(self):
        assert is_integrations_enabled() is True


@pytest.mark.unit
class TestErrorCodes:

    @pytest.mark.parametrize('code', [
        AppErrorCode.INT_CONNECTOR_NOT_FOUND,
        AppErrorCode.INT_TIMEOUT,
        AppErrorCode.INT_DUPLICATE_IDEMPOTENT,
        AppErrorCode.INT_DISABLED,
        AppErrorCode.INT_CONNECTION_FAILED,
        AppErrorCode.INT_INVALID_MAPPING,
    ])
    def test_int_codes_registered(self, code):
        assert code in ERROR_REGISTRY
