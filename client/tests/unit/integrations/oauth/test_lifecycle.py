"""Unit tests — Integration Application status machine."""

import pytest

from client.features.integrations.oauth.client.domain import lifecycle
from client.features.integrations.oauth.client.models import IntegrationApplicationStatus
from core.errors import AppErrorCode, ConflictException


@pytest.mark.unit
class TestLifecycle:

    def test_constants_match_model_choices(self):
        assert {lifecycle.ACTIVE, lifecycle.DISABLED, lifecycle.REVOKED} == {
            c.value for c in IntegrationApplicationStatus
        }

    def test_transition_sources(self):
        assert lifecycle.TRANSITION_SOURCES[lifecycle.ACTIVE] == {lifecycle.DISABLED}
        assert lifecycle.TRANSITION_SOURCES[lifecycle.DISABLED] == {lifecycle.ACTIVE}
        assert lifecycle.TRANSITION_SOURCES[lifecycle.REVOKED] == {lifecycle.ACTIVE, lifecycle.DISABLED}

    def test_revoked_never_a_source(self):
        assert all(lifecycle.REVOKED not in src for src in lifecycle.TRANSITION_SOURCES.values())

    @pytest.mark.parametrize('status', [lifecycle.ACTIVE, lifecycle.DISABLED])
    def test_ensure_mutable_ok(self, status):
        lifecycle.ensure_mutable(status)

    def test_ensure_mutable_revoked(self):
        with pytest.raises(ConflictException) as exc:
            lifecycle.ensure_mutable(lifecycle.REVOKED)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_REVOKED

    def test_ensure_deletable_ok(self):
        lifecycle.ensure_deletable(lifecycle.REVOKED)

    @pytest.mark.parametrize('status', [lifecycle.ACTIVE, lifecycle.DISABLED])
    def test_ensure_deletable_rejects_live(self, status):
        with pytest.raises(ConflictException) as exc:
            lifecycle.ensure_deletable(status)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_NOT_REVOKED
