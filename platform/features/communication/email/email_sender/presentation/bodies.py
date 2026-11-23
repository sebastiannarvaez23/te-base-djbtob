from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_CODE = r'^[A-Z0-9_]+$'


class CreateEmailSenderBody(RequestBody):
    code = Field(str, max_length=80, pattern=_CODE)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    email = Field(str, is_email=True)
    reply_to = Field(str, required=False, is_email=True, default='')
    is_default = Field(bool, required=False, default=False)
    is_active = Field(bool, required=False, default=True)


class UpdateEmailSenderBody(RequestBody):
    code = Field(str, required=False, max_length=80, pattern=_CODE)
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    email = Field(str, required=False, is_email=True)
    reply_to = Field(str, required=False, is_email=True)
    is_default = Field(bool, required=False)
    is_active = Field(bool, required=False)
