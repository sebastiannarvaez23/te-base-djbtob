"""HTTP 429 goes through the global handler as RL_001 + Retry-After."""
from __future__ import annotations

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import RequestFactory
from rest_framework.exceptions import Throttled

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AuthException, RateLimitException
from core.errors.handler import app_exception_handler
from core.errors.retry_after import RETRY_AFTER_HEADER

import re

import pytest

pytestmark = pytest.mark.unit


def _ctx():
    request = RequestFactory().get('/api/v1/things/')
    request.request_id = 'req-rl'
    return {'request': request, 'view': None}


def test_drf_throttled_is_rl_001_with_retry_after():
    response = app_exception_handler(Throttled(wait=12.2), _ctx())

    assert response.status_code == 429
    assert response.data['error']['code'] == 'RL_001'
    assert response.data['error']['retry_after'] == 13
    assert 'retry_after' not in (response.data['error'].get('context') or {})
    assert response.has_header(RETRY_AFTER_HEADER)
    assert response[RETRY_AFTER_HEADER] == '13'
    assert response.data['error']['trace_id'] == 'req-rl'
    assert response.data['message'] == 'Too many requests'
    assert response.data['detail'] == 'Too many requests.'


def test_throttled_envelope_stays_english_under_spanish_locale():
    from django.utils import translation

    with translation.override('es'):
        response = app_exception_handler(Throttled(wait=5), _ctx())

    assert response.data['message'] == 'Too many requests'
    assert response.data['detail'] == 'Too many requests.'
    body = f"{response.data['message']} {response.data['detail']}"
    assert not re.search(r'[áéíóúñüÁÉÍÓÚÑÜ¿¡]', body)


def test_drf_throttled_without_wait_omits_retry_after():
    response = app_exception_handler(Throttled(), _ctx())

    assert response.status_code == 429
    assert response.data['error']['code'] == 'RL_001'
    assert 'retry_after' not in response.data['error']
    assert not response.has_header(RETRY_AFTER_HEADER)


def test_rate_limit_exception_uses_rl_001():
    response = app_exception_handler(RateLimitException(retry_after=4), _ctx())

    assert response.status_code == 429
    assert response.data['error']['code'] == AppErrorCode.RATE_LIMITED.value
    assert response.data['error']['retry_after'] == 4
    assert response[RETRY_AFTER_HEADER] == '4'


def test_domain_429_promotes_retry_after_out_of_context():
    exc = AuthException(AppErrorCode.AUTH_LOGIN_LOCKED, retry_after=90)
    response = app_exception_handler(exc, _ctx())

    assert response.status_code == 429
    assert response.data['error']['code'] == 'AUTH_017'
    assert response.data['error']['retry_after'] == 90
    assert 'retry_after' not in (response.data['error'].get('context') or {})
    assert response[RETRY_AFTER_HEADER] == '90'


def test_domain_429_without_wait_has_no_header():
    response = app_exception_handler(
        AuthException(AppErrorCode.AUTH_LOGIN_LOCKED),
        _ctx(),
    )

    assert response.status_code == 429
    assert 'retry_after' not in response.data['error']
    assert not response.has_header(RETRY_AFTER_HEADER)


def test_throttled_envelope_shape_has_no_incident():
    response = app_exception_handler(Throttled(wait=2), _ctx())

    assert response.data['type'] == 'error'
    assert response.data['status_code'] == 429
    assert set(response.data['error']) >= {'code', 'trace_id', 'retry_after'}
    assert 'incident' not in response.data['error']
    assert 'errors' not in response.data['error']


def test_fractional_wait_under_one_second_becomes_one():
    response = app_exception_handler(Throttled(wait=0.1), _ctx())

    assert response.data['error']['retry_after'] == 1
    assert response[RETRY_AFTER_HEADER] == '1'


def test_non_429_does_not_emit_retry_after_header():
    from core.errors.exceptions import ValidationAppException

    response = app_exception_handler(
        ValidationAppException(AppErrorCode.VALIDATION_ERROR, retry_after=10),
        _ctx(),
    )

    assert response.status_code == 400
    assert 'retry_after' not in response.data['error']
    assert not response.has_header(RETRY_AFTER_HEADER)


def test_flatten_drf_errors_stringifies_lazy_in_english():
    from django.utils import translation

    from core.errors.drf_messages import flatten_drf_errors

    class _Lazy:
        code = 'custom_en'

        def __str__(self):
            lang = translation.get_language() or ''
            if lang.startswith('en'):
                return 'Custom english detail.'
            return 'Detalle en español.'

    with translation.override('es'):
        errors = flatten_drf_errors(_Lazy())

    assert errors == [{
        'field': '__all__',
        'code': 'custom_en',
        'detail': 'Custom english detail.',
    }]


def test_flatten_forced_spanish_error_detail_uses_code_catalog():
    from django.utils import translation
    from rest_framework.exceptions import ErrorDetail

    from core.errors.drf_messages import flatten_drf_errors

    forced = ErrorDetail('Este campo es obligatorio.', code='required')
    with translation.override('es'):
        errors = flatten_drf_errors({'email': [forced]})

    assert errors == [{
        'field': 'email',
        'code': 'required',
        'detail': 'This field is required.',
    }]


def test_flatten_unknown_spanish_code_falls_back_to_invalid_value():
    from rest_framework.exceptions import ErrorDetail

    from core.errors.drf_messages import flatten_drf_errors

    forced = ErrorDetail('Valor inválido personalizado.', code='custom_biz')
    errors = flatten_drf_errors(forced)

    assert errors[0]['detail'] == 'Invalid value.'
    assert errors[0]['code'] == 'custom_biz'


def test_http404_uses_http_001_from_registry():
    from django.http import Http404

    response = app_exception_handler(Http404('gone'), _ctx())

    assert response.status_code == 404
    assert response.data['message'] == 'Resource not found'
    assert response.data['detail'] == (
        'The requested resource does not exist or was deleted.'
    )
    assert response.data['error']['code'] == 'HTTP_001'
    assert 'incident' not in response.data['error']
