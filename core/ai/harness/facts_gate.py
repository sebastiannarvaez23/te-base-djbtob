"""Gate duro: no afirmar hechos de bodega sin tool exitoso."""

from __future__ import annotations

import re

# Señales de afirmaciones operativas (ES/EN). Chitchat corto sin dígitos pasa.
_FACT_KEYWORDS = re.compile(
    r'(?i)\b('
    r'pedidos?|ordenes?|órdenes?|orders?|stock|inventarios?|inventory|'
    r'bodegas?|warehouses?|'
    r'skus?|referencias?|references?|picking|packing|ubicaci[oó]n(?:es)?|locations?|'
    r'cantidades?|quantit(?:y|ies)|saldos?|balances?|lotes?|lots?|series?|serials?|'
    r'recib\w*|receiv\w*|despach\w*|ship\w*|fulfill\w*'
    r')\b'
)
_HAS_DIGIT = re.compile(r'\d')


def looks_like_warehouse_fact(text: str) -> bool:
    """True si el texto parece afirmar datos operativos de bodega."""
    cleaned = (text or '').strip()
    if not cleaned:
        return False
    if _HAS_DIGIT.search(cleaned) and _FACT_KEYWORDS.search(cleaned):
        return True
    if _FACT_KEYWORDS.search(cleaned) and len(cleaned) > 40:
        return True
    return False


def enforce_tool_before_facts(
    text: str,
    *,
    require_tool_before_facts: bool,
    orientation: bool,
    had_successful_tool: bool,
    out_of_scope_message: str,
) -> str:
    """
    Si la policy exige tool-before-facts y no hubo tool exitoso, reemplaza
    afirmaciones de bodega por el mensaje out-of-scope. Orientation y chitchat
    seguro no se tocan.
    """
    if not require_tool_before_facts or orientation or had_successful_tool:
        return text
    cleaned = (text or '').strip()
    out = (out_of_scope_message or '').strip()
    if out and cleaned == out:
        return text
    if looks_like_warehouse_fact(cleaned):
        return out or cleaned
    return text
