from client.features.logging.ops.operations.domain.schemas import RECENT_ACTIVITY_LIMIT, TraceScope
from core.query import QueryFilter, QueryParam
from core.validators.codes import ValidationCode
from core.validators.core import ValidationError


class RecentActivityQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    limit = QueryParam(coerce=int, min_value=1, max_value=RECENT_ACTIVITY_LIMIT)


class RecordTraceQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    # Required unless ``scope`` asks for a whole warehouse surface.
    reference_id = QueryParam(coerce=str, is_uuid=True)
    reference_type = QueryParam(
        coerce=str,
        max_length=100,
        pattern=r'^[A-Za-z][A-Za-z0-9_]{0,99}$',
    )
    warehouse_id = QueryParam(coerce=str, is_uuid=True)
    scope = QueryParam(coerce=str, choices=[scope.value for scope in TraceScope])

    def validate(self) -> tuple:
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        if 'scope' in self._filters:
            needed, excluded = 'warehouse_id', ('reference_id', 'reference_type')
        else:
            needed, excluded = 'reference_id', ()
        if needed not in self._filters:
            errors.append(ValidationError(
                field=needed,
                code=ValidationCode.REQUIRED,
                detail=f"Query param '{needed}' is required.",
            ))
        errors.extend(
            ValidationError(
                field=name,
                code=ValidationCode.CONFLICTING_FIELD,
                detail=f"Query param '{name}' cannot be combined with 'scope'.",
            )
            for name in excluded if name in self._filters
        )
        return not errors, errors
