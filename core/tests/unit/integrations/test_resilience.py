"""Matriz escenario 11 — Circuit breaker."""

import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ServerException
from core.integrations.infrastructure.resilience import assert_circuit_closed, with_transient_retries


@pytest.mark.unit
class TestResilience:

    def test_circuit_opens_after_threshold(self, settings):
        settings.INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD = 2
        cid = 'conn-1'

        def fail():
            raise ConnectionError('down')

        for _ in range(2):
            with pytest.raises(ConnectionError):
                with_transient_retries(fail, max_attempts=1, connection_id=cid)

        with pytest.raises(ServerException) as exc:
            assert_circuit_closed(cid)
        assert exc.value.code == AppErrorCode.INT_PROVIDER_UNAVAILABLE
