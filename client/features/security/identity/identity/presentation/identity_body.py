from core.validators import ValidationCode, ValidationError

from client.features.security.lifecycle.registration.domain.identity import apply_identity_fields


def merge_identity_body(data: dict) -> tuple[dict, list[ValidationError]]:
    """Apply shared identity normalisation to a RequestBody payload."""
    cleaned, raw_errors = apply_identity_fields(data)
    errors = []
    for field, code, detail in raw_errors:
        try:
            validation_code = ValidationCode(code)
        except ValueError:
            validation_code = ValidationCode.INVALID_PATTERN
        errors.append(ValidationError(field=field, code=validation_code, detail=detail))
    return cleaned, errors
