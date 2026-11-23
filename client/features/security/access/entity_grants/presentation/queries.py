from core.query import QueryFilter, QueryParam
from core.validators import ValidationCode, ValidationError
from client.features.security.access.entity_grants.presentation.bodies import ENTITY_TYPES


class GrantSetQuery(QueryFilter):
    """Conjunto completo, acotado por ``MAX_GRANTS_PER_REQUEST``."""

    ALLOW_UNPAGINATED = True

    entity_type = QueryParam(coerce=str, choices=ENTITY_TYPES)

    def validate(self):
        ok, errors = super().validate()
        if 'entity_type' not in self._params:
            errors.append(ValidationError(
                'entity_type',
                ValidationCode.REQUIRED,
                "Query param 'entity_type' is required.",
            ))
            ok = False
        return ok, errors
