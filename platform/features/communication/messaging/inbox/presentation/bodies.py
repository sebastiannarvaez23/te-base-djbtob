from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class AdminNotifyBody(RequestBody):
    title = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    body = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    level = Field(str, required=False, choices=['INFO', 'SUCCESS', 'WARNING'], default='INFO')
    scope = Field(str, choices=['SINGLE_USER', 'COMPANY_USERS', 'ALL_TENANTS'])
    target_company_id = Field(str, required=False, nullable=True, is_uuid=True)
    target_user_id = Field(str, required=False, nullable=True, is_uuid=True)


class ResourceTypeCreateBody(RequestBody):
    code = Field(str, max_length=80, pattern=PATTERN_CODE)
    label = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    icon = Field(str, required=False, max_length=80, default='', pattern=PATTERN_CONTENT)
    route_template = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class ResourceTypeUpdateBody(RequestBody):
    label = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    icon = Field(str, required=False, max_length=80, pattern=PATTERN_CONTENT)
    route_template = Field(str, required=False, max_length=255, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)
