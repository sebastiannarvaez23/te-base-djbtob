from core.validators import Field, RequestBody

from platform.features.security.access.functionalities.domain.categories import FUNCTIONALITY_CATEGORIES
from platform.features.security.access.functionalities.domain.offering import BILLING_MODES, OFFERINGS
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

_CATEGORIES = list(FUNCTIONALITY_CATEGORIES)
_OFFERINGS = list(OFFERINGS)
_BILLING_MODES = list(BILLING_MODES)


class CreateFunctionalityBody(RequestBody):
    key      = Field(str, required=True,  min_length=2, max_length=100, pattern=PATTERN_CODE)
    label    = Field(str, required=True,  min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    module   = Field(str, required=True,  min_length=1, max_length=100, pattern=PATTERN_CONTENT)
    category = Field(str, required=False, max_length=50, choices=_CATEGORIES)
    offering = Field(str, required=False, max_length=20, choices=_OFFERINGS, default='plan')
    billing_mode = Field(str, required=False, max_length=20, choices=_BILLING_MODES, default='included')
    catalog_service_id = Field(str, required=False, nullable=True, is_uuid=True)


class UpdateFunctionalityBody(RequestBody):
    key      = Field(str,  required=False, min_length=2, max_length=100, pattern=PATTERN_CODE)
    label    = Field(str,  required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    module   = Field(str,  required=False, min_length=1, max_length=100, pattern=PATTERN_CONTENT)
    category = Field(str,  required=False, max_length=50, choices=_CATEGORIES)
    offering = Field(str, required=False, max_length=20, choices=_OFFERINGS)
    billing_mode = Field(str, required=False, max_length=20, choices=_BILLING_MODES)
    catalog_service_id = Field(str, required=False, nullable=True, is_uuid=True)
    is_active = Field(None, required=False)


class AssignFunctionalityBody(RequestBody):
    module = Field(str, required=True, min_length=1, max_length=100, pattern=PATTERN_CONTENT)
