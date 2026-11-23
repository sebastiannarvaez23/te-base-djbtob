from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT


class CreateSupportSessionBody(RequestBody):
    motive = Field(str, required=True, min_length=1, max_length=4000, pattern=PATTERN_CONTENT)


class SendSupportMessageBody(RequestBody):
    body = Field(str, required=True, min_length=1, max_length=4000, pattern=PATTERN_CONTENT)


class RateSupportSessionBody(RequestBody):
    rating = Field(int, required=True, min_value=1, max_value=5)
    comment = Field(str, required=False, default='', max_length=500, pattern=PATTERN_CONTENT)


class UpdateSupportSettingsBody(RequestBody):
    queue_wait_timeout_minutes = Field(int, required=False, min_value=1, max_value=180)
    whatsapp_url = Field(str, required=False, max_length=500, pattern=PATTERN_CONTENT)
    phone_line = Field(str, required=False, max_length=64, pattern=PATTERN_CONTENT)
