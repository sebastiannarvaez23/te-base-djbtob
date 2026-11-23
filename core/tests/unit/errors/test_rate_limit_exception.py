"""RateLimitException and AppException.retry_after (RL_001)."""
from __future__ import annotations

import pytest

from core.errors import AppErrorCode, ERROR_REGISTRY
from core.errors.exceptions import (
    AuthException,
    OnboardingException,
    RateLimitException,
    ValidationAppException,
)


pytestmark = pytest.mark.unit


def test_unknown_error_code_raises_english_value_error():
    from core.errors.exceptions import AppException

    with pytest.raises(ValueError, match=r'Unknown error code:'):
        AppException(object())  # type: ignore[arg-type]


def test_rate_limit_exception_has_no_code_override():
    import inspect

    assert 'code' not in inspect.signature(RateLimitException.__init__).parameters


def test_rate_limit_exception_defaults_to_rl_001():
    exc = RateLimitException(retry_after=12.2)

    assert exc.code is AppErrorCode.RATE_LIMITED
    assert exc.http_status == 429
    assert exc.message == 'Too many requests'
    assert exc.detail == 'Too many requests.'
    assert exc.retry_after == 13
    assert exc.context['retry_after'] == 13


def test_rate_limit_exception_without_wait():
    exc = RateLimitException()

    assert exc.http_status == 429
    assert exc.retry_after is None
    assert 'retry_after' not in exc.context


def test_rate_limit_exception_reads_wait_from_context():
    exc = RateLimitException(context={'retry_after': '7', 'scope': 'anon'})

    assert exc.retry_after == 7
    assert exc.context['scope'] == 'anon'


def test_rate_limit_exception_rejects_invalid_wait():
    exc = RateLimitException(retry_after=0)

    assert exc.retry_after is None
    assert 'retry_after' not in exc.context


def test_domain_429_accepts_retry_after_kwarg():
    locked = AuthException(AppErrorCode.AUTH_LOGIN_LOCKED, retry_after=90)
    throttled = OnboardingException(
        AppErrorCode.ONBOARDING_RESEND_THROTTLED,
        retry_after=3,
    )

    assert locked.retry_after == 90
    assert locked.http_status == 429
    assert throttled.retry_after == 3
    assert throttled.http_status == 429


def test_non_429_exception_may_carry_retry_after_but_is_not_rate_limited():
    exc = ValidationAppException(AppErrorCode.VALIDATION_ERROR, retry_after=10)

    assert ERROR_REGISTRY[exc.code]['http_status'] == 400
    assert exc.retry_after == 10
