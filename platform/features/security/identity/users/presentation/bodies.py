from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT, PATTERN_PHONE


class CreateAdminUserBody(RequestBody):
    username = Field(str, max_length=150, pattern=PATTERN_CONTENT)
    email = Field(str, is_email=True)
    first_name = Field(str, max_length=100, pattern=PATTERN_CONTENT)
    last_name = Field(str, max_length=100, pattern=PATTERN_CONTENT)
    telephone = Field(str, required=False, max_length=100, default='', pattern=PATTERN_PHONE)
    password = Field(str, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    rol_id = Field(str, is_uuid=True)
    is_superuser = Field(bool, required=False, default=False)


class UpdateAdminUserBody(RequestBody):
    username = Field(str, required=False, max_length=150, pattern=PATTERN_CONTENT)
    email = Field(str, required=False, is_email=True)
    first_name = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    last_name = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    telephone = Field(str, required=False, max_length=100, pattern=PATTERN_PHONE)
    password = Field(str, required=False, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    rol_id = Field(str, required=False, is_uuid=True)
    is_superuser = Field(bool, required=False)
