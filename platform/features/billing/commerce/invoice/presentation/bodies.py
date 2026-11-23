from decimal import Decimal

from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateInvoiceBody(RequestBody):
    invoice_number = Field(str, required=True, min_length=2, max_length=50, pattern=PATTERN_CONTENT)
    company = Field(str, required=True, is_uuid=True)
    subscription = Field(str, required=True, is_uuid=True)
    issue_date = Field(str, required=True, min_length=10, max_length=10, pattern=PATTERN_CONTENT)
    due_date = Field(str, required=True, min_length=10, max_length=10, pattern=PATTERN_CONTENT)
    total_amount = Field(Decimal, required=True, min_value=0)
    currency = Field(str, required=False, max_length=3, default='USD', pattern=PATTERN_CODE)
    status = Field(str, required=False, min_length=2, max_length=20, default='pending', pattern=PATTERN_CODE)
    notes = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    metadata = Field(dict, required=False, default=dict)


class UpdateInvoiceStatusBody(RequestBody):
    status = Field(str, required=True, min_length=2, max_length=20, pattern=PATTERN_CODE)


class ResendInvoiceBody(RequestBody):
    recipient_email = Field(str, required=True, is_email=True)
