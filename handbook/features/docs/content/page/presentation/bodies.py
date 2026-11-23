from core.validators import Field, RequestBody
from handbook.core.constants import AUDIENCES, HTTP_METHODS, KINDS, LOCALES
from necore.query.patterns import PATTERN_CONTENT


class LocaleVersionBody(RequestBody):
    locale = Field(str, choices=sorted(LOCALES), max_length=2)
    version = Field(str, max_length=16, pattern=r'^\d+\.\d+(?:\.\d+)?$')
    title = Field(str, min_length=1, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, default='', max_length=2000, pattern=PATTERN_CONTENT)
    markdown = Field(str, min_length=1, max_length=2_000_000, pattern=PATTERN_CONTENT)


class SavePageBody(RequestBody):
    slug = Field(str, min_length=1, max_length=80, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    parent_id = Field(str, required=False, nullable=True, default=None, is_uuid=True)
    show_in_sidebar = Field(bool, required=False, default=True)
    audience = Field(str, choices=sorted(AUDIENCES))
    kind = Field(str, choices=sorted(KINDS))
    client_feature_id = Field(str, required=False, nullable=True, default=None, is_uuid=True)
    admin_feature_id = Field(str, required=False, nullable=True, default=None, is_uuid=True)
    sort_order = Field(int, required=False, default=0, min_value=0, max_value=10000)
    icon = Field(str, required=False, default='', max_length=80, pattern=r'^[a-z0-9-]*$')
    menu_title = Field(str, required=False, default='', max_length=200, pattern=PATTERN_CONTENT)
    http_method = Field(str, required=False, default='', choices=[''] + sorted(HTTP_METHODS), max_length=8)
    versions = Field(list, required=False, default=list, item=LocaleVersionBody, max_items=24)


class SubmitChangeBody(RequestBody):
    page_id = Field(str, is_uuid=True)
    reason = Field(str, min_length=10, max_length=2000, pattern=PATTERN_CONTENT)


class ReviewChangeBody(RequestBody):
    review_note = Field(str, required=False, default='', max_length=2000, pattern=PATTERN_CONTENT)
