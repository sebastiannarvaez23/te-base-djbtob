from core.query import QueryFilter, QueryParam
from core.validators import ValidationCode, ValidationError
from client.features.security.identity.module_filters.presentation.bodies import MODULE_KEYS


class ModuleFilterListQuery(QueryFilter):
    """Full list: a user keeps at most 20 filters per module."""

    ALLOW_UNPAGINATED = True

    module_key = QueryParam(coerce=str, choices=MODULE_KEYS)

    def validate(self):
        ok, errors = super().validate()
        if 'module_key' not in self._params:
            errors.append(ValidationError(
                'module_key',
                ValidationCode.REQUIRED,
                "Query param 'module_key' is required.",
            ))
            ok = False
        return ok, errors
