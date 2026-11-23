"""Códigos de error — geografía / locaciones."""
from enum import Enum


class GeographyErrorCode(str, Enum):
    GEO_COUNTRY_NOT_FOUND = 'GEO_001'
    GEO_COUNTRY_DUPLICATE = 'GEO_002'
    GEO_DEPARTMENT_NOT_FOUND = 'GEO_003'
    GEO_DEPARTMENT_DUPLICATE = 'GEO_004'
    GEO_CITY_NOT_FOUND = 'GEO_005'
    GEO_CITY_DUPLICATE = 'GEO_006'
    GEO_IMPORT_INVALID_FILE = 'GEO_007'
    GEO_IMPORT_ROW_INVALID = 'GEO_008'
    GEO_COUNTRY_INACTIVE = 'GEO_009'
    GEO_CITY_INACTIVE = 'GEO_010'
    GEO_COUNTRY_IN_USE = 'GEO_011'
    GEO_DEPARTMENT_IN_USE = 'GEO_012'
    GEO_CITY_IN_USE = 'GEO_013'
    GEO_CURRENCY_NOT_FOUND = 'GEO_014'
    GEO_CURRENCY_DUPLICATE = 'GEO_015'
    GEO_CURRENCY_INACTIVE = 'GEO_016'
    GEO_COUNTRY_CURRENCY_NOT_FOUND = 'GEO_017'
    GEO_CURRENCY_NOT_ALLOWED = 'GEO_018'
    GEO_COUNTRY_CURRENCY_DUPLICATE = 'GEO_019'
    GEO_CURRENCY_IN_USE = 'GEO_020'


GEO_REGISTRY: dict[GeographyErrorCode, dict] = {
    GeographyErrorCode.GEO_COUNTRY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Country not found',
        'detail': 'The requested country does not exist in the locations master.',
    },
    GeographyErrorCode.GEO_COUNTRY_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate country code',
        'detail': 'A country with that code already exists.',
    },
    GeographyErrorCode.GEO_DEPARTMENT_NOT_FOUND: {
        'http_status': 404,
        'message': 'Department not found',
        'detail': 'The requested department does not exist.',
    },
    GeographyErrorCode.GEO_DEPARTMENT_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate department code',
        'detail': 'A department with that code already exists for this country.',
    },
    GeographyErrorCode.GEO_CITY_NOT_FOUND: {
        'http_status': 404,
        'message': 'City not found',
        'detail': 'The requested city does not exist.',
    },
    GeographyErrorCode.GEO_CITY_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate city code',
        'detail': 'A city with that code already exists for this department.',
    },
    GeographyErrorCode.GEO_IMPORT_INVALID_FILE: {
        'http_status': 400,
        'message': 'Invalid locations import file',
        'detail': 'The uploaded file is missing, empty, or not a valid CSV template.',
    },
    GeographyErrorCode.GEO_IMPORT_ROW_INVALID: {
        'http_status': 400,
        'message': 'Invalid locations import row',
        'detail': 'One or more rows in the import file could not be processed.',
    },
    GeographyErrorCode.GEO_COUNTRY_INACTIVE: {
        'http_status': 409,
        'message': 'Country inactive',
        'detail': 'The country exists but is inactive. Activate it before using it in policies.',
    },
    GeographyErrorCode.GEO_CITY_INACTIVE: {
        'http_status': 409,
        'message': 'City inactive',
        'detail': 'The city exists but is inactive. Choose an active city for the company location.',
    },
    GeographyErrorCode.GEO_COUNTRY_IN_USE: {
        'http_status': 409,
        'message': 'Country in use',
        'detail': 'This country cannot be deleted because departments or related records still reference it.',
    },
    GeographyErrorCode.GEO_DEPARTMENT_IN_USE: {
        'http_status': 409,
        'message': 'Department in use',
        'detail': 'This department cannot be deleted because cities or related records still reference it.',
    },
    GeographyErrorCode.GEO_CITY_IN_USE: {
        'http_status': 409,
        'message': 'City in use',
        'detail': 'This city cannot be deleted because companies or related records still reference it.',
    },
    GeographyErrorCode.GEO_CURRENCY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Currency not found',
        'detail': 'The requested currency does not exist in the currency master.',
    },
    GeographyErrorCode.GEO_CURRENCY_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate currency code',
        'detail': 'A currency with that ISO 4217 code already exists.',
    },
    GeographyErrorCode.GEO_CURRENCY_INACTIVE: {
        'http_status': 409,
        'message': 'Currency inactive',
        'detail': 'The currency exists but is inactive. Activate it before linking it to a country or charge.',
    },
    GeographyErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Country currency link not found',
        'detail': 'The requested country–currency association does not exist.',
    },
    GeographyErrorCode.GEO_CURRENCY_NOT_ALLOWED: {
        'http_status': 400,
        'message': 'Currency not allowed for country',
        'detail': 'That currency is not enabled for the selected country.',
    },
    GeographyErrorCode.GEO_COUNTRY_CURRENCY_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate country currency',
        'detail': 'That currency is already linked to this country.',
    },
    GeographyErrorCode.GEO_CURRENCY_IN_USE: {
        'http_status': 409,
        'message': 'Currency in use',
        'detail': 'This currency cannot be deleted because one or more countries still reference it.',
    },
}

__all__ = ['GeographyErrorCode', 'GEO_REGISTRY']
