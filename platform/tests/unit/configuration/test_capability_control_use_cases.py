"""Unit tests — capability control admin."""

from __future__ import annotations

import pytest

from core.errors import ValidationAppException

from platform.features.configuration.ai.capability_control.application.use_cases import (
    GetCapabilityControlUseCase,
    UpdateCapabilityControlUseCase,
)
from platform.features.configuration.ai.capability_control.domain.schemas import (
    CONTROL_CAPABILITIES,
    CapabilityStubSchema,
    default_capabilities,
)


class MemoryRepo:
    def __init__(self):
        self.items = default_capabilities()
        self.updated_at = None

    def get_all(self):
        return list(self.items)

    def save_all(self, items):
        self.items = list(items)
        return self.items

    def get_updated_at(self):
        return self.updated_at


class FakeHealth:
    def probe(self, provider: str) -> str:
        return 'ok'


@pytest.mark.unit
class TestCapabilityControl:

    def test_get_covers_catalog(self):
        result = GetCapabilityControlUseCase(MemoryRepo(), FakeHealth()).execute()
        assert {c.key for c in result.capabilities} == set(CONTROL_CAPABILITIES)

    def test_update_persists(self):
        repo = MemoryRepo()
        body = {
            'capabilities': [
                {
                    'key': c.key,
                    'enabled': c.key == 'forecast',
                    'provider': 'fake',
                    'notes': 'x' if c.key == 'forecast' else '',
                }
                for c in default_capabilities()
            ],
        }
        result = UpdateCapabilityControlUseCase(repo, FakeHealth()).execute(body)
        forecast = next(c for c in result.capabilities if c.key == 'forecast')
        assert forecast.enabled is True
        assert forecast.notes == 'x'

    def test_update_rejects_partial(self):
        with pytest.raises(ValidationAppException):
            UpdateCapabilityControlUseCase(MemoryRepo(), FakeHealth()).execute({
                'capabilities': [
                    CapabilityStubSchema(key='forecast').model_dump(),
                ],
            })
