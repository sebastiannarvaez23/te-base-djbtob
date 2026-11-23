from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateSectionBody(RequestBody):
    code  = Field(str, required=True, min_length=2, max_length=50, pattern=PATTERN_CODE)
    name  = Field(str, required=True, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    icon  = Field(str, required=False, max_length=100, default='', pattern=PATTERN_CONTENT)
    order = Field(int, required=False)


class UpdateSectionBody(RequestBody):
    code      = Field(str, required=False, min_length=2, max_length=50, pattern=PATTERN_CODE)
    name      = Field(str, required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    icon      = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    order     = Field(int, required=False)
    is_active = Field(bool, required=False)


class ReorderSectionBody(RequestBody):
    ids = Field(list, min_items=1, max_items=500)
