from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateConnectorDefinitionBody(RequestBody):
    key = Field(str, max_length=50, pattern=PATTERN_CODE)
    kind = Field(str, max_length=20, pattern=PATTERN_CODE)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    version = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='1.0')
    capabilities = Field(list, required=False, default=list)
    config_schema = Field(dict, required=False, default=dict)
    is_active = Field(bool, required=False, default=True)


class UpdateConnectorDefinitionBody(RequestBody):
    kind = Field(str, required=False, max_length=20, pattern=PATTERN_CODE)
    name = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    version = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    capabilities = Field(list, required=False)
    config_schema = Field(dict, required=False)
    is_active = Field(bool, required=False)
