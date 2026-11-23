"""Format optional UI snapshot for the agent system prompt (English)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

_UI_CONTEXT_KEYS = (
    'route',
    'module_id',
    'module_code',
    'module_name',
    'feature_key',
    'page_section',
    'page_section_label',
    'module_purpose',
    'entity_type',
    'entity_id',
)

_HUMAN_KEYS = (
    'module_name',
    'page_section_label',
    'module_purpose',
)

_INTERNAL_KEYS = (
    'route',
    'module_code',
    'module_id',
    'feature_key',
    'page_section',
    'entity_type',
    'entity_id',
)

_HUMAN_LABELS = {
    'module_name': 'Module',
    'page_section_label': 'Tab',
    'module_purpose': 'Purpose',
}

_INTERNAL_LABELS = {
    'route': 'Route',
    'module_code': 'Module code',
    'module_id': 'Module id',
    'feature_key': 'Feature',
    'page_section': 'Page section key',
    'entity_type': 'Entity type',
    'entity_id': 'Entity id',
}


def normalize_ui_context(raw: Optional[Mapping[str, Any]]) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, str] = {}
    for key in _UI_CONTEXT_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out


def format_ui_context_for_prompt(raw: Optional[Mapping[str, Any]]) -> str:
    """
    Compact English block for the system prompt.

    Human fields first (safe to quote). Internal fields are routing-only.
    Empty when there is nothing useful — callers skip injection.
    """
    ctx = normalize_ui_context(raw)
    if not ctx:
        return ''

    lines = [
        'Operator screen context:',
        'For orientation questions, answer from Visible fields only; do not invent data.',
    ]

    human = [k for k in _HUMAN_KEYS if k in ctx]
    if human:
        lines.append('Visible to operator (use in answers):')
        for key in human:
            lines.append(f'- {_HUMAN_LABELS[key]}: {ctx[key]}')

    internal = [k for k in _INTERNAL_KEYS if k in ctx]
    if internal:
        lines.append('Internal only (routing; never quote to the user):')
        for key in internal:
            lines.append(f'- {_INTERNAL_LABELS[key]}: {ctx[key]}')

    return '\n'.join(lines)
