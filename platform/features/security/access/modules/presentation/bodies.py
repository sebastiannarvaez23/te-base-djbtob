from core.validators import Field, RequestBody, ValidationCode, ValidationError
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

from platform.features.security.access.functionalities.domain.offering import BILLING_MODES, OFFERINGS


def require_route_when_sidebar(validated: dict, *, create: bool) -> list[ValidationError]:
    """Route is mandatory only when the module is shown in the sidebar."""
    route = validated.get('route')
    if isinstance(route, str):
        validated['route'] = route.strip()
        route = validated['route']

    if create:
        in_sidebar = validated.get('is_sidebar', True)
        if in_sidebar and not route:
            return [_route_required_error()]
        return []

    if validated.get('is_sidebar') is True and not route:
        return [_route_required_error()]
    return []


def _route_required_error() -> ValidationError:
    return ValidationError(
        field='route',
        code=ValidationCode.REQUIRED,
        detail="Field 'route' is required when the module is shown in the sidebar.",
    )


class CreateModuleBody(RequestBody):
    code        = Field(str,  required=True,  min_length=2, max_length=100, pattern=PATTERN_CODE)
    name        = Field(str,  required=True,  min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str,  required=False, max_length=500, pattern=PATTERN_CONTENT)
    icon        = Field(str,  required=True,  min_length=2, max_length=100, pattern=PATTERN_CONTENT)
    route       = Field(str,  required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    section_id  = Field(str,  required=True, is_uuid=True)
    order       = Field(int,  required=False)
    is_sidebar  = Field(bool, required=False, default=True)
    offering = Field(str, required=False, max_length=20, choices=list(OFFERINGS), default='plan')
    billing_mode = Field(str, required=False, max_length=20, choices=list(BILLING_MODES), default='included')
    catalog_service_id = Field(str, required=False, nullable=True, is_uuid=True)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        extra = require_route_when_sidebar(self.validated_data, create=True)
        if extra:
            return False, extra
        return True, []


class UpdateModuleBody(RequestBody):
    # `code` is immutable after create — sending it yields UNKNOWN_FIELD.
    name        = Field(str,  required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str,  required=False, max_length=500, pattern=PATTERN_CONTENT)
    icon        = Field(str,  required=False, min_length=2, max_length=100, pattern=PATTERN_CONTENT)
    route       = Field(str,  required=False, max_length=255, pattern=PATTERN_CONTENT)
    section_id  = Field(str,  required=False, is_uuid=True)
    order       = Field(int,  required=False)
    is_sidebar  = Field(bool, required=False)
    offering = Field(str, required=False, max_length=20, choices=list(OFFERINGS))
    billing_mode = Field(str, required=False, max_length=20, choices=list(BILLING_MODES))
    catalog_service_id = Field(str, required=False, nullable=True, is_uuid=True)
    is_active   = Field(None, required=False)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        extra = require_route_when_sidebar(self.validated_data, create=False)
        if extra:
            return False, extra
        return True, []


class ReorderModuleBody(RequestBody):
    ids = Field(list, min_items=1, max_items=500)
