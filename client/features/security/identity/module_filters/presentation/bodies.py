from core.validators import Field, RequestBody
from client.features.security.identity.module_filters.domain.schemas import (
    MAX_ZONES_PER_FILTER,
    ModuleKey,
)
from necore.query.patterns import PATTERN_CONTENT

MODULE_KEYS = [item.value for item in ModuleKey]

class FilterCriteriaBody(RequestBody):
    warehouse_id = Field(str, is_uuid=True)
    zone_ids = Field(
        list, required=False, item=str, is_uuid=True, max_items=MAX_ZONES_PER_FILTER, default=[],
    )

class CreateModuleFilterBody(RequestBody):
    module_key = Field(str, choices=MODULE_KEYS)
    name = Field(str, min_length=1, max_length=80, pattern=PATTERN_CONTENT)
    criteria = Field(dict, schema=FilterCriteriaBody)
    activate = Field(bool, required=False, default=False)

class UpdateModuleFilterBody(RequestBody):
    name = Field(str, required=False, min_length=1, max_length=80, pattern=PATTERN_CONTENT)
    criteria = Field(dict, required=False, schema=FilterCriteriaBody)

class DeactivateModuleFiltersBody(RequestBody):
    module_key = Field(str, choices=MODULE_KEYS)
