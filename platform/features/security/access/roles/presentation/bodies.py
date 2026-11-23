from core.validators import Field, RequestBody
from platform.features.security.access.modules.presentation.bodies import require_route_when_sidebar
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateAdminRoleBody(RequestBody):
    name = Field(str, max_length=100, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class UpdateAdminRoleBody(RequestBody):
    name = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=255, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)


class UpdateAdminRoleFeaturesBody(RequestBody):
    feature_keys = Field(list, required=True)
    module_codes = Field(list, required=False, default=list)


class CreateAdminSectionBody(RequestBody):
    code = Field(str, max_length=50, pattern=PATTERN_CODE)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    icon = Field(str, required=False, max_length=100, default='', pattern=PATTERN_CONTENT)
    order = Field(int, required=False, min_value=0, default=0)


class UpdateAdminSectionBody(RequestBody):
    code = Field(str, required=False, max_length=50, pattern=PATTERN_CODE)
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    icon = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    order = Field(int, required=False, min_value=0)
    is_active = Field(bool, required=False)


class CreateAdminModuleBody(RequestBody):
    code = Field(str, max_length=100, pattern=PATTERN_CODE)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=500, default='', pattern=PATTERN_CONTENT)
    icon = Field(str, max_length=100, pattern=PATTERN_CONTENT)
    route = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    section_id = Field(str, is_uuid=True)
    order = Field(int, required=False, min_value=0, default=0)
    is_sidebar = Field(bool, required=False, default=True)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        extra = require_route_when_sidebar(self.validated_data, create=True)
        if extra:
            return False, extra
        return True, []


class UpdateAdminModuleBody(RequestBody):
    # `code` is immutable after create — sending it yields UNKNOWN_FIELD.
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, required=False, max_length=500, pattern=PATTERN_CONTENT)
    icon = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    route = Field(str, required=False, max_length=255, pattern=PATTERN_CONTENT)
    section_id = Field(str, required=False, is_uuid=True)
    order = Field(int, required=False, min_value=0)
    is_sidebar = Field(bool, required=False)
    is_active = Field(bool, required=False)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        extra = require_route_when_sidebar(self.validated_data, create=False)
        if extra:
            return False, extra
        return True, []


class CreateAdminFeatureBody(RequestBody):
    module = Field(str, max_length=100, pattern=PATTERN_CONTENT)
    key = Field(str, max_length=100, pattern=PATTERN_CODE)
    label = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    category = Field(str, required=False, max_length=50, default='features', pattern=PATTERN_CONTENT)


class UpdateAdminFeatureBody(RequestBody):
    module = Field(str, required=False, max_length=100, pattern=PATTERN_CONTENT)
    key = Field(str, required=False, max_length=100, pattern=PATTERN_CODE)
    label = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    category = Field(str, required=False, max_length=50, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)


class ReorderCatalogBody(RequestBody):
    ids = Field(list, min_items=1, max_items=500)
