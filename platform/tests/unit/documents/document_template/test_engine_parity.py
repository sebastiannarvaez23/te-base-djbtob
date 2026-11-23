"""Backend half of the cross-engine parity suite.

Loads shared fixtures (`parity_fixtures.json`) and asserts the Jinja
engine produces the documented `expected` output for every case. The
frontend has a mirror suite that loads the same fixture file (copied
into base-admin-web/docs) and asserts the Mustache engine matches.

If you change syntax behavior on either side, update the fixture and
both suites — they are the contract.
"""
import json
from pathlib import Path

import pytest

from platform.features.documents.document_template.document_template.infrastructure.jinja_template_engine import (
    JinjaTemplateEngine,
)


_FIXTURE_PATH = Path(__file__).parent / 'parity_fixtures.json'


def _load_fixtures():
    with _FIXTURE_PATH.open('r', encoding='utf-8') as f:
        payload = json.load(f)
    return payload['cases']


@pytest.fixture(scope='module')
def engine():
    return JinjaTemplateEngine()


@pytest.mark.parametrize('case', _load_fixtures(), ids=lambda c: c['name'])
def test_jinja_matches_parity_fixture(engine, case):
    result = engine.interpolate(case['template'], case['data'])
    assert result == case['expected'], (
        f"Parity violation in case '{case['name']}': "
        f"got {result!r}, expected {case['expected']!r}"
    )
