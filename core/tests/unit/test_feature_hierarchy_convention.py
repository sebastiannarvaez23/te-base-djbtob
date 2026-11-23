"""Convention: Clean Architecture layers must not sit on feature L2 roots.

L1 = mundo (client|platform|handbook)
L2 = feature extractable — NO domain/application/infrastructure/presentation
L3 = lógica conjunta — NO CA
L4 = entidad — CA only here

See README.md § Jerarquía de features and
.cursor/rules/monolith-feature-hierarchy.mdc.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
WORLDS = ('client', 'platform', 'handbook')
CA_LAYERS = ('domain', 'application', 'infrastructure', 'presentation')


def _l2_dirs() -> list[Path]:
    found: list[Path] = []
    for world in WORLDS:
        features = REPO_ROOT / world / 'features'
        if not features.is_dir():
            continue
        for child in sorted(features.iterdir()):
            if child.is_dir() and not child.name.startswith('_') and child.name != '__pycache__':
                found.append(child)
    return found


def test_no_clean_architecture_on_feature_l2_roots():
    """Fail if any L2 package has CA layers at its root."""
    violations: list[str] = []
    for l2 in _l2_dirs():
        for layer in CA_LAYERS:
            if (l2 / layer).is_dir():
                violations.append(f'{l2.relative_to(REPO_ROOT).as_posix()}/{layer}')
    assert violations == [], (
        'CA layers found on L2 feature roots (must live only on L4 entities):\n'
        + '\n'.join(f'  - {v}' for v in violations)
    )


HELPER_NAMES = frozenset({
    'foundation',
    'facade',
    'common',
    'notification',
})


def test_known_helpers_have_no_ca_layer_dirs():
    """Helpers under an L2 must not pretend incomplete Clean Architecture."""
    violations: list[str] = []
    for l2 in _l2_dirs():
        for child in sorted(l2.iterdir()):
            if not child.is_dir() or child.name not in HELPER_NAMES:
                continue
            for layer in CA_LAYERS:
                if (child / layer).is_dir():
                    violations.append(
                        f'{child.relative_to(REPO_ROOT).as_posix()}/{layer}'
                    )
    assert violations == [], (
        'Helper packages must be flat (no domain/application/…):\n'
        + '\n'.join(f'  - {v}' for v in violations)
    )


def test_known_l2_features_exist():
    """Smoke: expected extractable L2 modules are present."""
    names = {p.name for p in _l2_dirs()}
    for expected in (
        'security',
        'logging',
        'communication',
        'integrations',
        'billing',
        'docs',
    ):
        assert expected in names, f'missing L2 feature {expected!r}; have {sorted(names)}'
