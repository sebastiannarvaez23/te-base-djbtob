"""
Runtime status codes for assistant (wire: ``assistant.status``).

The agent emits stable ``code`` values while work is in progress; the frontend
maps each code to i18n copy + an animated icon. English ``label`` is a fallback
for clients without translations.

``still_working`` is a UX reassurance shown by the frontend when a phase lasts
longer than ~10s; it is listed here so ``/status`` and i18n stay aligned.
"""

from __future__ import annotations

# Stable wire codes (never rename lightly — frontends key off these).
ASSISTANT_STATUS_INTERPRETING = 'interpreting'
ASSISTANT_STATUS_SEARCHING_ORDERS = 'searching_orders'
ASSISTANT_STATUS_SEARCHING_REFERENCES = 'searching_references'
ASSISTANT_STATUS_SEARCHING_WAREHOUSES = 'searching_warehouses'
ASSISTANT_STATUS_CALCULATING = 'calculating'
ASSISTANT_STATUS_REVIEWING_RESULTS = 'reviewing_results'
ASSISTANT_STATUS_COMPOSING = 'composing'
ASSISTANT_STATUS_STILL_WORKING = 'still_working'

ASSISTANT_STATUS_CODES = (
    ASSISTANT_STATUS_INTERPRETING,
    ASSISTANT_STATUS_SEARCHING_ORDERS,
    ASSISTANT_STATUS_SEARCHING_REFERENCES,
    ASSISTANT_STATUS_SEARCHING_WAREHOUSES,
    ASSISTANT_STATUS_CALCULATING,
    ASSISTANT_STATUS_REVIEWING_RESULTS,
    ASSISTANT_STATUS_COMPOSING,
    ASSISTANT_STATUS_STILL_WORKING,
)

ASSISTANT_STATUS_LABELS: dict[str, str] = {
    ASSISTANT_STATUS_INTERPRETING: 'Interpreting your request…',
    ASSISTANT_STATUS_SEARCHING_ORDERS: 'Searching warehouse orders…',
    ASSISTANT_STATUS_SEARCHING_REFERENCES: 'Organizing catalog references…',
    ASSISTANT_STATUS_SEARCHING_WAREHOUSES: 'Listing warehouses…',
    ASSISTANT_STATUS_CALCULATING: 'Calculating indicators…',
    ASSISTANT_STATUS_REVIEWING_RESULTS: 'Reviewing results…',
    ASSISTANT_STATUS_COMPOSING: 'Writing a reply…',
    ASSISTANT_STATUS_STILL_WORKING: 'Still working on your request…',
}

# Tool whitelist → operator-facing process status.
_TOOL_STATUS_MAP: dict[str, str] = {
    'list_orders': ASSISTANT_STATUS_SEARCHING_ORDERS,
    'get_order_by_number': ASSISTANT_STATUS_SEARCHING_ORDERS,
    'get_order_indicators': ASSISTANT_STATUS_CALCULATING,
    'list_references': ASSISTANT_STATUS_SEARCHING_REFERENCES,
    'get_reference': ASSISTANT_STATUS_SEARCHING_REFERENCES,
    'list_warehouses': ASSISTANT_STATUS_SEARCHING_WAREHOUSES,
}


def status_for_tool(tool_name: str) -> str:
    """Map a tool key to a runtime status code (fallback: interpreting)."""
    return _TOOL_STATUS_MAP.get((tool_name or '').strip(), ASSISTANT_STATUS_INTERPRETING)


def status_payload(code: str) -> dict[str, str]:
    """Wire payload for ``assistant.status``."""
    key = (code or ASSISTANT_STATUS_INTERPRETING).strip()
    if key not in ASSISTANT_STATUS_LABELS:
        key = ASSISTANT_STATUS_INTERPRETING
    return {
        'code': key,
        'label': ASSISTANT_STATUS_LABELS[key],
    }
