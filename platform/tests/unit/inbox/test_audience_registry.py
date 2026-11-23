"""Tests del registry de resolución de audiencia (selección de estrategia)."""

import uuid
from unittest.mock import MagicMock

import pytest

from platform.features.communication.messaging.inbox.domain.enums import AudienceScope
from platform.features.communication.messaging.inbox.domain.schemas import Audience, RecipientGroup
from platform.features.communication.messaging.inbox.infrastructure.audience.resolvers import (
    AudienceResolverRegistry,
)

pytestmark = pytest.mark.unit


def test_registry_dispatches_to_matching_strategy():
    group = RecipientGroup(schema_name='acme', user_ids=[uuid.uuid4()])
    strategy = MagicMock()
    strategy.resolve.return_value = [group]
    registry = AudienceResolverRegistry({AudienceScope.SINGLE_USER: strategy})

    audience = Audience(scope=AudienceScope.SINGLE_USER, target_user_id=uuid.uuid4())
    result = registry.resolve(audience)

    strategy.resolve.assert_called_once_with(audience)
    assert result == [group]


def test_registry_returns_empty_for_unregistered_scope():
    registry = AudienceResolverRegistry({})
    result = registry.resolve(Audience(scope=AudienceScope.ALL_TENANTS))
    assert result == []


def test_default_registry_wires_all_scopes():
    registry = AudienceResolverRegistry.default()
    assert set(registry._strategies.keys()) == {
        AudienceScope.SINGLE_USER,
        AudienceScope.COMPANY_USERS,
        AudienceScope.ALL_TENANTS,
    }
