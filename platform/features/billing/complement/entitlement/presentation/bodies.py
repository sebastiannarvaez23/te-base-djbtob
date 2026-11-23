from core.validators import Field, RequestBody, ValidationCode, ValidationError
from necore.query.patterns import PATTERN_CONTENT


class GrantComplementBody(RequestBody):
    functionality_id = Field(str, required=False, nullable=True, is_uuid=True)
    module_id = Field(str, required=False, nullable=True, is_uuid=True)
    notes = Field(str, required=False, default='', max_length=2000, pattern=PATTERN_CONTENT)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        has_functionality = self.validated_data.get('functionality_id') is not None
        has_module = self.validated_data.get('module_id') is not None
        if has_functionality == has_module:
            errors.append(ValidationError(
                field='functionality_id',
                code=ValidationCode.REQUIRED,
                detail="Send either functionality_id or module_id.",
            ))
            return False, errors
        return True, []


class RevokeComplementBody(RequestBody):
    notes = Field(str, required=False, default='', max_length=2000, pattern=PATTERN_CONTENT)
