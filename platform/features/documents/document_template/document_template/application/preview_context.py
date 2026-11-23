"""
Helpers for admin preview endpoints (no real tenant / invoice context).

Production renders inject ``tenant_code`` via SystemVarsBuilder(tenant=...)
and path fields like ``number`` via the billing data layer. The editor only
has mock_data, so previews need small, explicit aliases to resolve the same
storage_path_template without inventing business data.
"""
from __future__ import annotations

from typing import Any


_PREVIEW_TENANT_CODE = 'demo_tenant'


def enrich_preview_path_context(
    data: dict[str, Any] | None,
    system_vars: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (data, system_vars) suitable for PathResolver in admin preview.

    - Ensures ``tenant_code`` exists in system_vars (admin has no tenant).
    - Maps ``invoice_number`` → ``number`` when the path template needs it
      (same rule as ``invoice_context._short_number``).
    """
    preview_data = dict(data or {})
    preview_vars = dict(system_vars or {})

    if 'tenant_code' not in preview_vars and 'tenant_code' not in preview_data:
        preview_vars['tenant_code'] = _PREVIEW_TENANT_CODE

    if 'number' not in preview_data and preview_data.get('invoice_number'):
        inv = str(preview_data['invoice_number'])
        preview_data['number'] = inv[4:] if inv.upper().startswith('INV-') else inv

    return preview_data, preview_vars
