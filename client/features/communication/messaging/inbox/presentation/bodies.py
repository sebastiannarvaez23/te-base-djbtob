from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class ShareBody(RequestBody):
    resource_type_code = Field(str, max_length=80, pattern=PATTERN_CODE)
    resource_id = Field(str, is_uuid=True)
    recipient_user_ids = Field(list, min_items=1)
    title = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    body = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    level = Field(str, required=False, choices=['INFO', 'SUCCESS', 'WARNING'], default='INFO')
