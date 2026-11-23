from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateCredentialBody(RequestBody):
    provider = Field(str, choices=['openai', 'anthropic'], max_length=40)
    api_key = Field(str, min_length=8, max_length=512, pattern=PATTERN_CODE)
    label = Field(str, required=False, default='', max_length=120, pattern=PATTERN_CONTENT)
    activate = Field(bool, required=False, default=True)


class UpdateCredentialBody(RequestBody):
    api_key = Field(str, required=False, min_length=8, max_length=512, pattern=PATTERN_CODE)
    label = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)
