from client.features.security.identity.identity.presentation.identity_body import merge_identity_body
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import DOCUMENT_NUMBER_MAX_LENGTH
from core.validators import (
    DATE_FORMAT_CHOICES,
    TIME_FORMAT_CHOICES,
    Field,
    IanaTimezoneBodyMixin,
    RequestBody,
    TimeFormatBodyMixin,
)
from necore.query.patterns import PATTERN_CONTENT

class UpdateUserPreferencesBody(IanaTimezoneBodyMixin, TimeFormatBodyMixin, RequestBody):
    language              = Field(str,  required=False, min_length=2,  max_length=5, pattern=PATTERN_CONTENT)
    theme                 = Field(str,  required=False, min_length=2,  max_length=10, pattern=PATTERN_CONTENT)
    timezone              = Field(str,  required=False, min_length=2,  max_length=60, pattern=PATTERN_CONTENT)
    date_format           = Field(str,  required=False, min_length=5,  max_length=12, choices=list(DATE_FORMAT_CHOICES))
    time_format           = Field(str,  required=False, min_length=2,  max_length=2,  choices=list(TIME_FORMAT_CHOICES))
    sidebar_collapsed     = Field(None, required=False)
    items_per_page        = Field(int,  required=False, min_value=5, max_value=200)
    notifications_enabled = Field(None, required=False)

class UpdateUserProfileBody(RequestBody):
    first_name         = Field(str, required=False, min_length=2, max_length=30, pattern=PATTERN_CONTENT)
    second_name        = Field(str, required=False, max_length=30, pattern=PATTERN_CONTENT)
    last_name          = Field(str, required=False, min_length=2, max_length=30, pattern=PATTERN_CONTENT)
    second_last_name   = Field(str, required=False, max_length=30, pattern=PATTERN_CONTENT)
    document_type      = Field(str, required=False, choices=list(IdentityDocumentType.values()))
    document_number    = Field(str, required=False, min_length=4, max_length=DOCUMENT_NUMBER_MAX_LENGTH, pattern=r'^[A-Za-z0-9.\-]+$')
    email              = Field(str, required=False, is_email=True)
    telephone          = Field(str, required=False, min_length=4, max_length=15, pattern=r'^\d+$')
    phone_country_code = Field(str, required=False, max_length=2, pattern=r'^[A-Za-z]{2}$')

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data, extra = merge_identity_body(dict(self._validated_data or {}))
        errors.extend(extra)
        self._validated_data = data
        return (len(errors) == 0), errors
