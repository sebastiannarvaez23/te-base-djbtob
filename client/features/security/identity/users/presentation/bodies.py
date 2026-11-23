from client.features.security.identity.identity.presentation.identity_body import merge_identity_body
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import DOCUMENT_NUMBER_MAX_LENGTH
from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT, PATTERN_PHONE


class CheckCompanyUsernameBody(RequestBody):
    username = Field(str, required=True, min_length=3, max_length=20, pattern=PATTERN_CONTENT)


class CheckCompanyEmailBody(RequestBody):
    email = Field(str, required=True, is_email=True, max_length=254)


class CreateCompanyUserBody(RequestBody):
    first_name       = Field(str, required=True,  min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_name      = Field(str, required=False, max_length=30, default='', pattern=PATTERN_CONTENT)
    last_name        = Field(str, required=True,  min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_last_name = Field(str, required=True,  min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    document_type    = Field(str, required=True, choices=list(IdentityDocumentType.values()))
    document_number  = Field(
        str, required=True, min_length=4, max_length=DOCUMENT_NUMBER_MAX_LENGTH,
        pattern=r'^[A-Za-z0-9.\-]+$',
    )
    birth_date       = Field(str, required=True, max_length=10, pattern=r'^\d{4}-\d{2}-\d{2}$')
    email            = Field(str, required=True,  is_email=True)
    username         = Field(str, required=True,  min_length=3,  max_length=20, pattern=PATTERN_CONTENT)
    telephone        = Field(str, required=True,  min_length=10, max_length=15, pattern=PATTERN_PHONE)
    password         = Field(str, required=False, min_length=8,  max_length=64, pattern=PATTERN_CONTENT)
    rol_id           = Field(str, required=True,  is_uuid=True)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data, extra = merge_identity_body(dict(self._validated_data or {}))
        errors.extend(extra)
        self._validated_data = data
        return (len(errors) == 0), errors


class UpdateCompanyUserBody(RequestBody):
    first_name       = Field(str, required=False, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_name      = Field(str, required=False, max_length=30, pattern=PATTERN_CONTENT)
    last_name        = Field(str, required=False, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_last_name = Field(str, required=False, max_length=30, pattern=PATTERN_CONTENT)
    document_type    = Field(str, required=False, choices=list(IdentityDocumentType.values()))
    document_number  = Field(
        str, required=False, min_length=4, max_length=DOCUMENT_NUMBER_MAX_LENGTH,
        pattern=r'^[A-Za-z0-9.\-]+$',
    )
    birth_date       = Field(str, required=False, max_length=10, pattern=r'^\d{4}-\d{2}-\d{2}$')
    email            = Field(str, required=False, is_email=True)
    telephone        = Field(str, required=False, min_length=10, max_length=15, pattern=PATTERN_PHONE)
    password         = Field(str, required=False, min_length=8,  max_length=64, pattern=PATTERN_CONTENT)
    rol_id           = Field(str, required=False, nullable=True,  is_uuid=True)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data, extra = merge_identity_body(dict(self._validated_data or {}))
        errors.extend(extra)
        self._validated_data = data
        return (len(errors) == 0), errors
