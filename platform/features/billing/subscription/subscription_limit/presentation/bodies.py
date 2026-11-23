from core.validators import Field, RequestBody, ValidationCode, ValidationError
from platform.features.billing.subscription.subscription_limit.domain.window import (
    VALIDATION_TYPES,
    WINDOW_HOURS_MAX,
    WINDOW_HOURS_MIN,
)
from necore.query.patterns import PATTERN_CONTENT

_VALIDATION_TYPES = list(VALIDATION_TYPES)

def _apply_window_hours_rules(data: dict, errors: list, *, require_if_window: bool) -> None:
    vtype = data.get('validation_type')
    hours = data.get('window_hours')
    if vtype == 'window':
        if require_if_window and hours is None:
            errors.append(ValidationError(
                field='window_hours',
                code=ValidationCode.REQUIRED,
                detail="Field 'window_hours' is required when validation_type is 'window'.",
            ))
    elif vtype in ('daily', 'lifetime'):
        data['window_hours'] = None

class CreateSubscriptionLimitBody(RequestBody):
    subscription = Field(str, is_uuid=True)
    functionality = Field(str, is_uuid=True)
    name = Field(str, required=False, max_length=150, default='', pattern=PATTERN_CONTENT)
    max_value = Field(int, min_value=0)
    validation_type = Field(
        str, required=False, choices=_VALIDATION_TYPES, default='lifetime',
    )
    window_hours = Field(
        int, required=False, min_value=WINDOW_HOURS_MIN, max_value=WINDOW_HOURS_MAX,
    )

    def validate(self):
        ok, errors = super().validate()
        _apply_window_hours_rules(self._validated_data, errors, require_if_window=True)
        return (len(errors) == 0), errors

class UpdateSubscriptionLimitBody(RequestBody):
    name = Field(str, required=False, max_length=150, pattern=PATTERN_CONTENT)
    max_value = Field(int, required=False, min_value=0)
    validation_type = Field(str, required=False, choices=_VALIDATION_TYPES)
    window_hours = Field(
        int, required=False, min_value=WINDOW_HOURS_MIN, max_value=WINDOW_HOURS_MAX,
    )

    def validate(self):
        ok, errors = super().validate()
        # Si se envía type=window sin hours, el use case puede reutilizar las hours
        # ya persistidas. Solo exige hours cuando vienen explícitamente como null.
        switching_to_window = self._validated_data.get('validation_type') == 'window'
        hours_explicit = 'window_hours' in self._data
        require = switching_to_window and hours_explicit and self._validated_data.get('window_hours') is None
        _apply_window_hours_rules(
            self._validated_data, errors, require_if_window=require,
        )
        return (len(errors) == 0), errors
