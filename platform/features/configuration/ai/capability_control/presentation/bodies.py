from core.ai.model_layer.catalog import AI_CHAT_PROVIDERS
from core.validators import Field, RequestBody

from platform.features.configuration.ai.capability_control.domain.schemas import (
    CONTROL_CAPABILITIES,
)
from necore.query.patterns import PATTERN_CONTENT

_SIZE = len(CONTROL_CAPABILITIES)
_PROVIDERS = list(AI_CHAT_PROVIDERS) + ['fake']
# de-dupe while preserving order
_PROVIDERS = list(dict.fromkeys(_PROVIDERS))

class CapabilityStubBody(RequestBody):
    key = Field(str, choices=list(CONTROL_CAPABILITIES), max_length=40, min_length=1)
    enabled = Field(bool, required=True)
    provider = Field(str, choices=_PROVIDERS, max_length=20, min_length=1)
    notes = Field(str, required=False, default='', max_length=200, min_length=0, pattern=PATTERN_CONTENT)

class UpdateCapabilityControlBody(RequestBody):
    capabilities = Field(list, item=CapabilityStubBody, min_items=_SIZE, max_items=_SIZE)
