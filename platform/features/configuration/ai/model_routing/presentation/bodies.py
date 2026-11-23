from core.ai.model_layer.catalog import AI_CAPABILITIES, AI_CHAT_PROVIDERS
from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_CAP_SIZE = len(AI_CAPABILITIES)


class ModelRouteBody(RequestBody):
    capability = Field(str, choices=list(AI_CAPABILITIES), max_length=40, min_length=1)
    provider = Field(str, choices=list(AI_CHAT_PROVIDERS), max_length=20, min_length=1)
    model_id = Field(str, required=False, default='', max_length=120, min_length=0, pattern=PATTERN_CONTENT)
    credential_source = Field(
        str, required=False, default='platform',
        choices=['platform', 'tenant_byok'], max_length=20,
    )
    fallbacks = Field(
        list, item=str, required=False, default=[], max_items=8,
    )
    max_tokens = Field(int, required=False, default=1024, min_value=1, max_value=128000)
    timeout_s = Field(float, required=False, default=60.0, min_value=1.0, max_value=600.0)
    max_cost_usd = Field(float, required=False, default=None, min_value=0.0)
    max_latency_ms = Field(int, required=False, default=None, min_value=100, max_value=600000)


class UpdateModelRoutingBody(RequestBody):
    routes = Field(list, item=ModelRouteBody, min_items=_CAP_SIZE, max_items=_CAP_SIZE)
    hourly_budget_usd = Field(float, required=False, default=None, min_value=0.0)
