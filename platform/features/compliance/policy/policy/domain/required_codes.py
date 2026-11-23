"""Códigos de políticas client obligatorias en el gate post-login / onboarding.

Fuente canónica de defaults. La lectura de Django settings vive en
``application.required_policy_codes`` (Clean Architecture: domain sin Django).
"""

from __future__ import annotations

from typing import Sequence, Tuple

# Fuente canónica por defecto. Mantener en mayúsculas (convención Policy.code).
DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES: Tuple[str, ...] = (
    'PRIVACY-POLICY',
    'TERMS-AND-CONDITIONS',
)

# Onboarding seals every code in the login list when the finalize body
# supplies the matching content hashes (privacy + terms today).
ONBOARDING_PRIVACY_POLICY_CODE = 'PRIVACY-POLICY'
ONBOARDING_TERMS_POLICY_CODE = 'TERMS-AND-CONDITIONS'


def normalize_policy_codes(codes: Sequence[str] | None) -> Tuple[str, ...]:
    if not codes:
        return ()
    seen: set[str] = set()
    out: list[str] = []
    for raw in codes:
        code = str(raw or '').strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return tuple(out)
