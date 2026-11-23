"""Shared identity-document and phone normalisation for onboarding and profile."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .enums import IdentityDocumentType

DOCUMENT_NUMBER_MIN_LENGTH = 4
DOCUMENT_NUMBER_MAX_LENGTH = 20
TELEPHONE_MIN_DIGITS = 4
TELEPHONE_MAX_DIGITS = 15
OPTIONAL_NAME_MIN_LENGTH = 2
MIN_BIRTH_AGE_YEARS = 18
MAX_BIRTH_AGE_YEARS = 120
NUMERIC_DOCUMENT_TYPES = frozenset({
    IdentityDocumentType.CEDULA_CIUDADANIA.value,
    IdentityDocumentType.CEDULA_EXTRANJERIA.value,
})


class IdentityFieldError(ValueError):
    """Field-scoped identity rule failure (mapped to RequestBody / Pydantic)."""

    def __init__(self, field: str, detail: str, code: str = 'INVALID_PATTERN'):
        self.field = field
        self.code = code
        super().__init__(detail)


def _document_type_code(value) -> str:
    if value is None:
        return ''
    if isinstance(value, IdentityDocumentType):
        return value.value
    return str(value).strip().upper()


def normalize_optional_person_name(value, field: str) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return ''
    if len(cleaned) < OPTIONAL_NAME_MIN_LENGTH:
        raise IdentityFieldError(
            field,
            f'{field} must be at least {OPTIONAL_NAME_MIN_LENGTH} characters when provided',
            code='MIN_LENGTH',
        )
    return cleaned


def normalize_phone_country_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    if not cleaned:
        return None
    if len(cleaned) != 2 or not cleaned.isalpha():
        raise IdentityFieldError(
            'phone_country_code',
            'phone_country_code must be an ISO 3166-1 alpha-2 code',
        )
    return cleaned


def normalize_document_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = _document_type_code(value)
    return cleaned or None


def normalize_document_number(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().upper().replace('.', '')
    if not cleaned:
        raise IdentityFieldError(
            'document_number',
            f'document_number must be between {DOCUMENT_NUMBER_MIN_LENGTH} and '
            f'{DOCUMENT_NUMBER_MAX_LENGTH} characters',
            code='MIN_LENGTH',
        )
    if len(cleaned) < DOCUMENT_NUMBER_MIN_LENGTH:
        raise IdentityFieldError(
            'document_number',
            f'document_number must be between {DOCUMENT_NUMBER_MIN_LENGTH} and '
            f'{DOCUMENT_NUMBER_MAX_LENGTH} characters',
            code='MIN_LENGTH',
        )
    if len(cleaned) > DOCUMENT_NUMBER_MAX_LENGTH:
        raise IdentityFieldError(
            'document_number',
            f'document_number must be between {DOCUMENT_NUMBER_MIN_LENGTH} and '
            f'{DOCUMENT_NUMBER_MAX_LENGTH} characters',
            code='MAX_LENGTH',
        )
    return cleaned


def _shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, month=2, day=28)


def normalize_birth_date(value) -> Optional[date]:
    """ISO calendar date, not in the future, between 18 and 120 years old."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            raise IdentityFieldError(
                'birth_date',
                'birth_date is required',
                code='REQUIRED',
            )
        try:
            parsed = date.fromisoformat(text[:10])
        except ValueError as exc:
            raise IdentityFieldError(
                'birth_date',
                'birth_date must be an ISO date (YYYY-MM-DD)',
            ) from exc
    today = date.today()
    if parsed > today:
        raise IdentityFieldError(
            'birth_date',
            'birth_date cannot be in the future',
            code='MAX_VALUE',
        )
    oldest = _shift_years(today, -MAX_BIRTH_AGE_YEARS)
    if parsed < oldest:
        raise IdentityFieldError(
            'birth_date',
            f'birth_date cannot be more than {MAX_BIRTH_AGE_YEARS} years ago',
            code='MIN_VALUE',
        )
    latest_allowed = _shift_years(today, -MIN_BIRTH_AGE_YEARS)
    if parsed > latest_allowed:
        raise IdentityFieldError(
            'birth_date',
            f'birth_date must be at least {MIN_BIRTH_AGE_YEARS} years ago',
            code='MAX_VALUE',
        )
    return parsed


def normalize_telephone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(cleaned) < TELEPHONE_MIN_DIGITS:
        raise IdentityFieldError(
            'telephone',
            f'telephone must contain at least {TELEPHONE_MIN_DIGITS} digits',
            code='MIN_LENGTH',
        )
    if len(cleaned) > TELEPHONE_MAX_DIGITS:
        raise IdentityFieldError(
            'telephone',
            f'telephone must contain at most {TELEPHONE_MAX_DIGITS} digits',
            code='MAX_LENGTH',
        )
    return cleaned


def assert_identity_invariants(
    *,
    document_type=None,
    document_number: Optional[str] = None,
    phone_country_code: Optional[str] = None,
    telephone: Optional[str] = None,
) -> None:
    """Cross-field rules. Skips a rule when either participating value is missing."""
    doc_type = _document_type_code(document_type)
    if doc_type and doc_type not in IdentityDocumentType.values():
        raise IdentityFieldError(
            'document_type',
            'document_type must be CC, CE or PA',
            code='INVALID_CHOICE',
        )
    number = document_number or ''
    if doc_type in NUMERIC_DOCUMENT_TYPES and number and not number.isdigit():
        raise IdentityFieldError(
            'document_number',
            'document_number must be numeric for this document type',
        )
    country = (phone_country_code or '').strip().upper()
    phone = telephone or ''
    if country == 'CO' and phone and len(phone) != 10:
        code = 'MIN_LENGTH' if len(phone) < 10 else 'MAX_LENGTH'
        raise IdentityFieldError(
            'telephone',
            'Colombian telephone numbers must have exactly 10 digits',
            code=code,
        )


def apply_identity_fields(data: dict) -> tuple[dict, list[tuple[str, str, str]]]:
    """Normalise identity keys present on a request payload.

    Returns ``(cleaned_data, errors)`` where each error is
    ``(field, ValidationCode value, detail)``.
    """
    errors: list[tuple[str, str, str]] = []
    out = dict(data)

    for field in ('second_name', 'second_last_name'):
        if field not in out:
            continue
        try:
            out[field] = normalize_optional_person_name(out.get(field), field=field) or ''
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    if 'phone_country_code' in out and out['phone_country_code']:
        try:
            out['phone_country_code'] = normalize_phone_country_code(out['phone_country_code'])
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    if 'document_type' in out and out['document_type'] is not None:
        try:
            cleaned_type = normalize_document_type(out['document_type'])
            out['document_type'] = cleaned_type
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    if 'document_number' in out and out.get('document_number') is not None:
        try:
            out['document_number'] = normalize_document_number(out.get('document_number'))
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    if 'telephone' in out and out.get('telephone') is not None:
        try:
            out['telephone'] = normalize_telephone(out.get('telephone'))
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    if 'birth_date' in out and out.get('birth_date') is not None:
        try:
            parsed = normalize_birth_date(out.get('birth_date'))
            out['birth_date'] = parsed.isoformat() if parsed else ''
        except IdentityFieldError as exc:
            errors.append((exc.field, exc.code, str(exc)))

    try:
        assert_identity_invariants(
            document_type=out.get('document_type'),
            document_number=out.get('document_number'),
            phone_country_code=out.get('phone_country_code'),
            telephone=out.get('telephone'),
        )
    except IdentityFieldError as exc:
        errors.append((exc.field, exc.code, str(exc)))

    return out, errors
