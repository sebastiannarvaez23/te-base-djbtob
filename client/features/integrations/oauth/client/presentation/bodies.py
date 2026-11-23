"""HTTP request bodies for Integration Application OAuth.

``core.validators.RequestBody`` already rejects unknown keys
(``UNKNOWN_FIELD``) and validates list items, patterns and sizes. Whether a
scope may be granted depends on the tenant catalog and is decided by the use
case, so the body only enforces the functionality-key shape.
"""
from __future__ import annotations

from core.validators import Field, RequestBody

from client.features.integrations.oauth.client.domain.schemas import (
    MAX_SCOPE_LENGTH,
    MAX_SCOPES,
    SCOPE_KEY_PATTERN,
)
from client.features.integrations.oauth.client.models import IntegrationApplicationEnvironment
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

_ENVIRONMENTS = sorted(c.value for c in IntegrationApplicationEnvironment)

def _scopes_field(*, required: bool) -> Field:
    return Field(
        list,
        required=required,
        item=str,
        pattern=SCOPE_KEY_PATTERN,
        max_length=MAX_SCOPE_LENGTH,
        min_items=1,
        max_items=MAX_SCOPES,
    )

class CreateIntegrationApplicationBody(RequestBody):
    name = Field(str, min_length=2, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=2000, default='', pattern=PATTERN_CONTENT)
    environment = Field(str, required=False, choices=_ENVIRONMENTS, default='CLIENT_TEST')
    scopes = _scopes_field(required=True)

class UpdateIntegrationApplicationBody(RequestBody):
    name = Field(str, required=False, min_length=2, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=2000, pattern=PATTERN_CONTENT)
    environment = Field(str, required=False, choices=_ENVIRONMENTS)
    scopes = _scopes_field(required=False)

class IssueTokenBody(RequestBody):
    grant_type = Field(str, min_length=1, max_length=64, pattern=PATTERN_CODE)
    client_id = Field(str, min_length=8, max_length=64, pattern=PATTERN_CODE)
    client_secret = Field(str, min_length=16, max_length=128, pattern=PATTERN_CONTENT)
    scope = Field(str, required=False, max_length=500, pattern=PATTERN_CONTENT)
