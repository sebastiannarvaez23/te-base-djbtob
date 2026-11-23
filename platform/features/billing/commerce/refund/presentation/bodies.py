from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT


class RefundPreviewBody(RequestBody):
    target_subscription_id = Field(str, is_uuid=True)


class CreateRefundBody(RequestBody):
    target_subscription_id = Field(str, is_uuid=True)


class RejectRefundBody(RequestBody):
    reason = Field(str, required=False, max_length=500, default='', pattern=PATTERN_CONTENT)
