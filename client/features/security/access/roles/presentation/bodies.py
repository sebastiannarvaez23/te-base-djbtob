from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT


class CreateRoleBody(RequestBody):
    name = Field(str, required=True, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=500, pattern=PATTERN_CONTENT)


class UpdateRoleBody(RequestBody):
    name = Field(str, required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=500, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)


class UpdateRoleFeaturesBody(RequestBody):
    feature_keys = Field(list, required=True)
    module_codes = Field(list, required=True)


class ToggleAccessBody(RequestBody):
    is_active = Field(bool, required=True)
