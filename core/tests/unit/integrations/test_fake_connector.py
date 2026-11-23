"""Matriz escenario 12 — FakeConnector."""

import pytest

from core.integrations.domain.enums import SyncDirection
from core.integrations.domain.schemas import SyncRequest
from core.integrations.infrastructure.fake_connector import FakeConnector

from .conftest import make_profile, make_sync_request


@pytest.mark.unit
class TestFakeConnector:

    def test_pull_push_dry_run_contract(self):
        profile = make_profile()
        connector = FakeConnector(pull_count=2, push_ok=True)
        pull = connector.pull_entities(make_sync_request(profile))
        assert pull.created == 2

        push = connector.push_entities(
            SyncRequest(
                profile=profile,
                entity='order',
                direction=SyncDirection.OUTBOUND,
                payload={'items': [{'external_id': 'A'}, {'external_id': 'B'}]},
            )
        )
        assert push.updated == 2

        dry = connector.dry_run(make_sync_request(profile))
        assert dry.would_create == 2
