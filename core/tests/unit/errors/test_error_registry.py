"""Registry completeness after splitting error codes by domain."""
from __future__ import annotations

import pytest

from core.errors import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import AuthException, ValidationAppException
from core.errors.sync_i18n import (
    ES_OVERRIDES,
    FRONTEND_ONLY_EN,
    FRONTEND_ONLY_ES,
    load_en_details,
)


pytestmark = pytest.mark.unit


def test_every_app_error_code_has_registry_entry():
    missing = [code.name for code in AppErrorCode if code not in ERROR_REGISTRY]
    extra = [code.name for code in ERROR_REGISTRY if code not in set(AppErrorCode)]
    assert missing == []
    assert extra == []
    assert len(AppErrorCode) == len(ERROR_REGISTRY)


def test_error_code_values_are_unique():
    values = [code.value for code in AppErrorCode]
    assert len(values) == len(set(values))


def test_composed_code_identity_and_lookup():
    code = AppErrorCode.AUTH_INVALID_CREDENTIALS
    assert code.value == 'AUTH_001'
    assert code is AppErrorCode['AUTH_INVALID_CREDENTIALS']
    assert ERROR_REGISTRY[code]['http_status'] == 401
    exc = AuthException(code)
    assert exc.code is code
    assert exc.http_status == 401


def test_validation_resolves_without_product_codes():
    assert AppErrorCode.VALIDATION_ERROR.value == 'VAL_001'
    assert not hasattr(AppErrorCode, 'PKG_TYPE_NOT_FOUND')
    exc = ValidationAppException(AppErrorCode.VALIDATION_ERROR)
    assert exc.code is AppErrorCode.VALIDATION_ERROR


def test_rate_limited_registry_is_english_429():
    code = AppErrorCode.RATE_LIMITED
    entry = ERROR_REGISTRY[code]
    assert code.value == 'RL_001'
    assert entry['http_status'] == 429
    assert entry['message'] == 'Too many requests'
    assert entry['detail'] == 'Too many requests.'
    assert ES_OVERRIDES['RL_001']
    assert load_en_details()['RL_001'] == 'Too many requests.'


def test_http_not_found_registry_is_english_404():
    code = AppErrorCode.HTTP_NOT_FOUND
    entry = ERROR_REGISTRY[code]
    assert code.value == 'HTTP_001'
    assert entry['http_status'] == 404
    assert entry['message'] == 'Resource not found'
    assert ES_OVERRIDES['HTTP_001']
    assert load_en_details()['HTTP_001'] == entry['detail']


def test_sync_i18n_covers_the_full_registry():
    en = load_en_details()
    assert set(en) == {code.value for code in AppErrorCode}
    assert set(ES_OVERRIDES) == set(en)


def test_frontend_only_retry_after_hints_stay_bilingual():
    assert FRONTEND_ONLY_EN['retry_after_seconds'] == (
        'Try again in {{retryAfter}} seconds.'
    )
    assert FRONTEND_ONLY_EN['retry_after_minutes'] == (
        'Try again in {{retryAfter}} minutes.'
    )
    assert FRONTEND_ONLY_ES['retry_after_seconds'] == (
        'Inténtalo de nuevo en {{retryAfter}} segundos.'
    )
    assert FRONTEND_ONLY_ES['retry_after_minutes'] == (
        'Inténtalo de nuevo en {{retryAfter}} minutos.'
    )
