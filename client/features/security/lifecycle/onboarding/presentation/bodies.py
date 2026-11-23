from datetime import datetime

from client.features.security.identity.identity.presentation.identity_body import merge_identity_body
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import DOCUMENT_NUMBER_MAX_LENGTH
from core.validators import Field, RequestBody, ValidationCode, ValidationError
from necore.query.patterns import PATTERN_CONTENT

# Cards expire on the LAST day of their month, so the only safe lower bound
# is the current calendar year — never hard-code a year here.
_CURRENT_YEAR = datetime.utcnow().year


class StartOnboardingBody(RequestBody):
    email = Field(str, required=True, is_email=True, max_length=254)


class ResumeOnboardingBody(RequestBody):
    token = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)


class ResendResumeLinkBody(RequestBody):
    email = Field(str, required=True, is_email=True, max_length=254)


class CompanyStepBody(RequestBody):
    name    = Field(str, required=True, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    nit     = Field(str, required=False, max_length=40, default='', pattern=PATTERN_CONTENT)
    is_registered = Field(bool, required=False, default=True)
    address = Field(str, required=True, min_length=5, max_length=255, pattern=PATTERN_CONTENT)
    country = Field(str, required=True, min_length=2, max_length=255, pattern=PATTERN_CONTENT)
    country_code = Field(str, required=True, max_length=2, pattern=r'^[A-Za-z]{2}$')
    state   = Field(str, required=True, min_length=2, max_length=255, pattern=PATTERN_CONTENT)
    city    = Field(str, required=True, min_length=2, max_length=255, pattern=PATTERN_CONTENT)
    city_id = Field(str, required=True, is_uuid=True)

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data = dict(self._validated_data or {})
        is_registered = bool(data.get('is_registered', True))
        nit = (data.get('nit') or '').strip()
        if is_registered:
            if len(nit) < 6:
                errors.append(ValidationError(
                    field='nit',
                    code=ValidationCode.MIN_LENGTH,
                    detail=(
                        "Field 'nit' must have at least 6 characters "
                        f"(received: {len(nit)})."
                    ),
                ))
            else:
                data['nit'] = nit
        else:
            data['nit'] = ''
        data['is_registered'] = is_registered
        self._validated_data = data
        return (len(errors) == 0), errors


class FinalizeOnboardingBody(RequestBody):
    privacy_accepted = Field(bool, required=True)
    privacy_content_hash = Field(
        str,
        required=True,
        min_length=64,
        max_length=64,
        pattern=r'^[a-fA-F0-9]{64}$',
    )
    privacy_country = Field(str, required=True, max_length=2, pattern=r'^[A-Za-z]{2}$')
    terms_accepted = Field(bool, required=True)
    terms_content_hash = Field(
        str,
        required=True,
        min_length=64,
        max_length=64,
        pattern=r'^[a-fA-F0-9]{64}$',
    )


class CheckUsernameBody(RequestBody):
    username = Field(str, required=True, min_length=4, max_length=20, pattern=PATTERN_CONTENT)


class AdminUserStepBody(RequestBody):
    email                 = Field(str, required=True, is_email=True)
    username              = Field(str, required=True, min_length=4,  max_length=20, pattern=PATTERN_CONTENT)
    telephone             = Field(str, required=True, min_length=4,  max_length=15, pattern=r'^\d+$')
    phone_country_code    = Field(str, required=True, max_length=2, pattern=r'^[A-Za-z]{2}$')
    # password is optional on re-edit: if a hash is already stored we keep it.
    # The use case still rejects empty password the *first* time the step runs.
    password              = Field(str, required=False, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    password_confirmation = Field(str, required=False, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    first_name            = Field(str, required=True, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_name           = Field(str, required=False, max_length=30, default='', pattern=PATTERN_CONTENT)
    last_name             = Field(str, required=True, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    second_last_name      = Field(str, required=True, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    document_type         = Field(str, required=True, choices=list(IdentityDocumentType.values()))
    document_number       = Field(
        str, required=True, min_length=4, max_length=DOCUMENT_NUMBER_MAX_LENGTH,
        pattern=r'^[A-Za-z0-9.\-]+$',
    )
    birth_date            = Field(str, required=True, max_length=10, pattern=r'^\d{4}-\d{2}-\d{2}$')

    def validate(self) -> tuple:
        ok, errors = super().validate()
        data, extra = merge_identity_body(dict(self._validated_data or {}))
        errors.extend(extra)
        self._validated_data = data
        return (len(errors) == 0), errors


class SubscriptionStepBody(RequestBody):
    subscription_id = Field(str, required=True, is_uuid=True)
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'], default='monthly')


class PaymentStepBody(RequestBody):
    processor_token = Field(str, required=True, min_length=8,  max_length=512, pattern=PATTERN_CONTENT)
    holder          = Field(str, required=True, min_length=2,  max_length=120, pattern=PATTERN_CONTENT)
    last4           = Field(str, required=True, min_length=4,  max_length=4, pattern=PATTERN_CONTENT)
    expiry_month    = Field(int, required=True, min_value=1,   max_value=12)
    expiry_year     = Field(int, required=True, min_value=_CURRENT_YEAR, max_value=_CURRENT_YEAR + 30)
