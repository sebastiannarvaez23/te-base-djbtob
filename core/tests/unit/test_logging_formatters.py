"""Unit tests for ColoredConsoleFormatter."""

import logging

import pytest

from core.logging_formatters import ColoredConsoleFormatter

pytestmark = pytest.mark.unit


def _record(level: int, msg: str = 'boom') -> logging.LogRecord:
    return logging.LogRecord(
        name='app.errors',
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_error_is_red_when_color_enabled():
    fmt = ColoredConsoleFormatter(
        fmt='{levelname} {message}', style='{', use_color=True,
    )
    out = fmt.format(_record(logging.ERROR))
    assert '\033[31m' in out
    assert out.endswith('\033[0m')
    assert 'ERROR boom' in out


def test_critical_is_bold_red():
    fmt = ColoredConsoleFormatter(
        fmt='{levelname} {message}', style='{', use_color=True,
    )
    out = fmt.format(_record(logging.CRITICAL))
    assert '\033[1;31m' in out


def test_warning_is_yellow():
    fmt = ColoredConsoleFormatter(
        fmt='{levelname} {message}', style='{', use_color=True,
    )
    out = fmt.format(_record(logging.WARNING))
    assert '\033[33m' in out


def test_info_has_no_ansi():
    fmt = ColoredConsoleFormatter(
        fmt='{levelname} {message}', style='{', use_color=True,
    )
    out = fmt.format(_record(logging.INFO, 'ok'))
    assert '\033[' not in out
    assert out == 'INFO ok'


def test_color_disabled_skips_ansi():
    fmt = ColoredConsoleFormatter(
        fmt='{levelname} {message}', style='{', use_color=False,
    )
    out = fmt.format(_record(logging.ERROR))
    assert '\033[' not in out
    assert out == 'ERROR boom'
