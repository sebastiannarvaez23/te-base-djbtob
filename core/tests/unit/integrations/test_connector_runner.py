"""Matriz escenarios 2–6 — ConnectorRunner."""

from __future__ import annotations

from concurrent.futures import TimeoutError as FuturesTimeoutError
from uuid import uuid4

import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ConflictException, ServerException, ValidationAppException
from core.integrations import run_connector_op
from core.integrations.application.connector_runner import ConnectorRunner
from core.integrations.domain.schemas import OperationContext
from core.integrations.infrastructure.fake_connector import FakeConnector
from core.integrations.infrastructure.idempotency import MemoryIdempotencyStore
from core.integrations.infrastructure.resilience import with_transient_retries
from core.integrations.observability import metrics

from .conftest import make_context, make_profile, make_sync_request


@pytest.mark.unit
class TestConnectorRunner:

    def test_successful_op_returns_result_and_metrics(self, monkeypatch):
        monkeypatch.setattr(
            'core.integrations.observability.integration_logger.log_integration_event',
            lambda **kwargs: None,
        )
        profile = make_profile()
        ctx = make_context(profile)
        result = run_connector_op(
            FakeConnector(pull_count=2).pull_entities,
            make_sync_request(profile),
            context=ctx,
            runner=ConnectorRunner(idempotency_store=MemoryIdempotencyStore()),
        )
        assert result.created == 2
        assert metrics.snapshot().get('integrations.success', 0) >= 1

    def test_timeout_raises_int_003(self, monkeypatch):
        profile = make_profile()
        ctx = make_context(profile)
        runner = ConnectorRunner(idempotency_store=MemoryIdempotencyStore())

        def _timeout(*_args, **_kwargs):
            raise FuturesTimeoutError()

        monkeypatch.setattr(runner, '_call_with_timeout', _timeout)
        with pytest.raises(ServerException) as exc:
            runner.run(FakeConnector().pull_entities, make_sync_request(profile), context=ctx)
        assert exc.value.code == AppErrorCode.INT_TIMEOUT

    def test_idempotency_hit_raises_int_006_without_reexecution(self):
        store = MemoryIdempotencyStore()
        runner = ConnectorRunner(idempotency_store=store)
        profile = make_profile()
        connector = FakeConnector(pull_count=5)
        ctx = OperationContext(
            connection_id=profile.connection_id,
            tenant_schema=profile.tenant_schema,
            operation='pull_entities',
            idempotency_key='fixed-key',
        )
        request = make_sync_request(profile)
        run_connector_op(connector.pull_entities, request, context=ctx, runner=runner)
        with pytest.raises(ConflictException) as exc:
            run_connector_op(connector.pull_entities, request, context=ctx, runner=runner)
        assert exc.value.code == AppErrorCode.INT_DUPLICATE_IDEMPOTENT

    def test_transient_error_is_retried(self):
        attempts = {'n': 0}

        def flaky():
            attempts['n'] += 1
            if attempts['n'] < 3:
                raise ConnectionError('temporary')
            return 'ok'

        assert with_transient_retries(flaky, max_attempts=3) == 'ok'
        assert attempts['n'] == 3

    def test_business_error_is_not_retried(self):
        attempts = {'n': 0}

        def business():
            attempts['n'] += 1
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)

        with pytest.raises(ValidationAppException):
            with_transient_retries(business, max_attempts=3)
        assert attempts['n'] == 1
