from core.validators import Field, RequestBody

from platform.features.security.access.functionalities.domain.categories import FUNCTIONALITY_CATEGORIES
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

_CATEGORIES = list(FUNCTIONALITY_CATEGORIES)


class CreateFeatureBody(RequestBody):
    module   = Field(str, required=True, max_length=100, pattern=PATTERN_CONTENT)
    key      = Field(str, required=True, max_length=200, pattern=PATTERN_CODE)
    label    = Field(str, required=True, max_length=200, pattern=PATTERN_CONTENT)
    category = Field(str, required=False, max_length=50, choices=_CATEGORIES)


class UpdateFeatureBody(RequestBody):
    label     = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    category  = Field(str, required=False, max_length=50, choices=_CATEGORIES)
    is_active = Field(bool, required=False)
