"""SyncOrchestrator — batch pull/push."""

import pytest

from core.integrations import SyncDirection, SyncOrchestrator
from core.integrations.application.connector_runner import ConnectorRunner
from core.integrations.domain.schemas import SyncRequest
from core.integrations.infrastructure.fake_connector import FakeConnector
from core.integrations.infrastructure.idempotency import MemoryIdempotencyStore

from .conftest import make_profile, make_sync_request


@pytest.mark.unit
class TestSyncOrchestrator:

    def test_batch_pull_and_push(self):
        profile = make_profile()
        connector = FakeConnector()
        orchestrator = SyncOrchestrator(
            runner=ConnectorRunner(idempotency_store=MemoryIdempotencyStore()),
        )
        result = orchestrator.run_batch(
            connector,
            profile,
            pull_request=make_sync_request(profile),
            push_request=SyncRequest(
                profile=profile,
                entity='order',
                direction=SyncDirection.OUTBOUND,
                payload={'items': [{'external_id': 'OUT-9'}]},
            ),
            request_id='test-req',
        )
        assert result.pull is not None and result.pull.created >= 1
        assert result.push is not None and result.push.updated >= 1
