from core.validators import Field, RequestBody, ValidationCode, ValidationError
from necore.query.patterns import PATTERN_CONTENT


class CreateCompanyBody(RequestBody):
    schema_name = Field(str, min_length=2, max_length=63, pattern=PATTERN_CONTENT)
    nit = Field(str, min_length=6, max_length=40, pattern=PATTERN_CONTENT)
    name = Field(str, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    address = Field(str, min_length=5, max_length=255, pattern=PATTERN_CONTENT)
    geo_city_id = Field(str, is_uuid=True)
    subscription = Field(str, is_uuid=True)
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'], default='monthly')


class UpdateCompanyBody(RequestBody):
    name = Field(str, required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    address = Field(str, required=False, min_length=5, max_length=255, pattern=PATTERN_CONTENT)
    nit = Field(str, required=False, max_length=40, pattern=PATTERN_CONTENT)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data = dict(self._validated_data or {})
        if 'nit' in data:
            nit = str(data.get('nit') or '').strip().replace('.', '')
            if nit and len(nit) < 6:
                errors.append(ValidationError(
                    field='nit',
                    code=ValidationCode.MIN_LENGTH,
                    detail=(
                        "Field 'nit' must have at least 6 characters "
                        f"(received: {len(nit)})."
                    ),
                ))
            data['nit'] = nit
        self._validated_data = data
        return (len(errors) == 0), errors


class CloseCompanyBody(RequestBody):
    reason = Field(str, required=True, min_length=3, max_length=500, pattern=PATTERN_CONTENT)


class SelfCloseCompanyBody(RequestBody):
    confirmation = Field(str, required=True, min_length=1, max_length=200, pattern=PATTERN_CONTENT)
    accepted = Field(bool, required=True)


class CompleteSelfCloseBody(RequestBody):
    reason = Field(str, required=False, min_length=0, max_length=500, default='', pattern=PATTERN_CONTENT)


class LegalHoldBody(RequestBody):
    enabled = Field(bool, required=True)
    reason = Field(str, required=False, min_length=0, max_length=500, default='', pattern=PATTERN_CONTENT)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data = dict(self._validated_data or {})
        reason = str(data.get('reason') or '').strip()
        data['reason'] = reason
        if data.get('enabled') and len(reason) < 3:
            errors.append(ValidationError(
                field='reason',
                code=ValidationCode.MIN_LENGTH,
                detail="Field 'reason' must have at least 3 characters when enabling a legal hold.",
            ))
        self._validated_data = data
        return (len(errors) == 0), errors


class ExportClosedTenantBody(RequestBody):
    waived = Field(bool, required=False, default=False)
    reason = Field(str, required=False, min_length=0, max_length=500, default='', pattern=PATTERN_CONTENT)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data = dict(self._validated_data or {})
        reason = str(data.get('reason') or '').strip()
        data['reason'] = reason
        if data.get('waived') and len(reason) < 3:
            errors.append(ValidationError(
                field='reason',
                code=ValidationCode.MIN_LENGTH,
                detail="Field 'reason' must have at least 3 characters when waiving export.",
            ))
        self._validated_data = data
        return (len(errors) == 0), errors


class PurgeClosedCompanyBody(RequestBody):
    force = Field(bool, required=False, default=False)
    reason = Field(str, required=False, min_length=0, max_length=500, default='', pattern=PATTERN_CONTENT)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data = dict(self._validated_data or {})
        reason = str(data.get('reason') or '').strip()
        data['reason'] = reason
        if data.get('force') and len(reason) < 3:
            errors.append(ValidationError(
                field='reason',
                code=ValidationCode.MIN_LENGTH,
                detail="Field 'reason' must have at least 3 characters for a forced purge.",
            ))
        self._validated_data = data
        return (len(errors) == 0), errors
