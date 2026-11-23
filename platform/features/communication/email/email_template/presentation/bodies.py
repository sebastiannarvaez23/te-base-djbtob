from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

_CODE = r'^[A-Z0-9_]+$'
_MAX_RECIPIENTS = 50


class CreateEmailTemplateBody(RequestBody):
    code = Field(str, max_length=80, pattern=_CODE)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    subject = Field(str, max_length=300, pattern=PATTERN_CONTENT)
    body = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    html_template = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    sender = Field(str, required=False, nullable=True, is_uuid=True, default=None)
    mock_data = Field(dict, required=False, default=dict)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    is_active = Field(bool, required=False, default=True)


class UpdateEmailTemplateBody(RequestBody):
    code = Field(str, required=False, max_length=80, pattern=_CODE)
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    subject = Field(str, required=False, max_length=300, pattern=PATTERN_CONTENT)
    body = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    html_template = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    sender = Field(str, required=False, nullable=True, is_uuid=True)
    mock_data = Field(dict, required=False)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    is_active = Field(bool, required=False)


class EmailAttachmentBody(RequestBody):
    filename = Field(str, min_length=1, max_length=255, pattern=PATTERN_CONTENT)
    content = Field(str, max_length=5000, pattern=PATTERN_CONTENT, min_length=1)
    mimetype = Field(str, required=False, default='application/octet-stream', max_length=127, pattern=PATTERN_CONTENT)


class SendEmailBody(RequestBody):
    template_code = Field(str, max_length=80, pattern=PATTERN_CODE)
    to = Field(list, min_items=1, max_items=_MAX_RECIPIENTS, item=str, is_email=True, max_length=254)
    context = Field(dict, required=False, default=dict)
    attachments = Field(list, required=False, default=list, item=EmailAttachmentBody, max_items=20)
    cc = Field(list, required=False, default=list, item=str, is_email=True, max_length=254, max_items=_MAX_RECIPIENTS)
    bcc = Field(list, required=False, default=list, item=str, is_email=True, max_length=254, max_items=_MAX_RECIPIENTS)
