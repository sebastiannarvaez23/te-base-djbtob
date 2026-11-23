from core.validators import Field, RequestBody
from core.query import PATTERN_CODE_UPPER_KEBAB, PATTERN_CONTENT

_COUNTRY = r'^[A-Za-z]{2}$'


class CreatePolicyBody(RequestBody):
    code = Field(str, max_length=80, pattern=PATTERN_CODE_UPPER_KEBAB)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    audience = Field(str, choices=['client', 'admin'])
    description = Field(str, required=False, default='', max_length=4000, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class UpdatePolicyBody(RequestBody):
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=4000, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)


class SavePolicyCountryDraftBody(RequestBody):
    title = Field(str, max_length=300, pattern=PATTERN_CONTENT)
    markdown = Field(str, required=False, default='', max_length=500_000, pattern=PATTERN_CONTENT)


class ReleasePolicyCountryDraftBody(RequestBody):
    change_summary = Field(str, required=False, default='', max_length=2000, pattern=PATTERN_CONTENT)


class SignPolicyBody(RequestBody):
    country = Field(str, max_length=2, pattern=_COUNTRY)
    channel = Field(str, required=False, default='web', max_length=32, pattern=r'^[a-z0-9_\-]+$')
