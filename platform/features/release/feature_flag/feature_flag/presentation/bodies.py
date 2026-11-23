from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_KEY = r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$'
_SCOPE_TYPES = ['COMPANY', 'USER', 'COUNTRY', 'STATE', 'CITY']
_FLAG_TYPES = ['RELEASE', 'OPS']
_STATUSES = ['DRAFT', 'ACTIVE', 'CERTIFIED', 'DISABLED', 'ARCHIVED']


class ScopeBody(RequestBody):
    scope_type = Field(str, choices=_SCOPE_TYPES)
    scope_value = Field(str, max_length=255, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class CreateFeatureFlagBody(RequestBody):
    key = Field(str, min_length=3, max_length=100, pattern=_KEY)
    name = Field(str, min_length=3, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    flag_type = Field(str, required=False, choices=_FLAG_TYPES, default='RELEASE')
    status = Field(str, required=False, choices=_STATUSES, default='DRAFT')
    enabled = Field(bool, required=False, default=False)
    owner = Field(str, required=False, max_length=120, default='', pattern=PATTERN_CONTENT)
    scopes = Field(list, required=False, item=ScopeBody, default=list)


class UpdateFeatureFlagBody(RequestBody):
    key = Field(str, required=False, min_length=3, max_length=100, pattern=_KEY)
    name = Field(str, required=False, min_length=3, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=255, pattern=PATTERN_CONTENT)
    flag_type = Field(str, required=False, choices=_FLAG_TYPES)
    status = Field(str, required=False, choices=_STATUSES)
    enabled = Field(bool, required=False)
    owner = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    scopes = Field(list, required=False, item=ScopeBody)


class ToggleFeatureFlagBody(RequestBody):
    enabled = Field(bool)


class SetFeatureFlagStatusBody(RequestBody):
    status = Field(str, choices=_STATUSES)
