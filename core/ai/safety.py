"""
core/ai/safety.py
─────────────────
Higiene de datos antes de que un prompt salga hacia un proveedor externo.

En un WMS B2B, cada llamada a un proveedor gestionado envía datos operativos del
tenant a un tercero. Este módulo reutiliza la fuente única de verdad de
enmascarado del proyecto (``core.logging_redaction``) para:

1. ``redact_for_log``  — versión enmascarada de un prompt, apta para logs/auditoría.
2. ``redact_prompt``   — enmascara secretos embebidos en el contenido de los
   mensajes antes de enviarlos al proveedor (best-effort sobre contenido JSON).

La redacción de PII de texto libre (nombres, direcciones) es un problema más
amplio; este módulo cubre secretos estructurados y deja el punto de extensión
centralizado. Ampliar aquí ⇒ se aplica a todas las features de IA por igual.
"""

import copy
import json

from core.logging_redaction import inline_json, mask_secrets

from .domain.schemas import Message, Prompt


def _redact_content(content: str) -> str:
    """Si el contenido es (o contiene) JSON, enmascara claves sensibles."""
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError):
        return content
    return json.dumps(mask_secrets(parsed), ensure_ascii=False)


def redact_prompt(prompt: Prompt) -> Prompt:
    """
    Devuelve una copia del prompt con secretos estructurados enmascarados.

    No muta el prompt original. Pensado para invocarse en el adaptador justo
    antes de enviar al proveedor.
    """
    clone = copy.deepcopy(prompt)
    if clone.system:
        clone.system = _redact_content(clone.system)
    clone.messages = [
        Message(role=m.role, content=_redact_content(m.content))
        for m in clone.messages
    ]
    return clone


def redact_for_log(prompt: Prompt, max_chars: int = 500) -> dict:
    """
    Representación segura y compacta de un prompt para logging/auditoría.

    Trunca el contenido y enmascara secretos. Nunca incluir el prompt crudo en
    logs; usar esta función.
    """
    def _trim(text: str) -> str:
        safe = inline_json(text) if text and text.strip().startswith(('{', '[')) else text
        return (safe[:max_chars] + '…') if safe and len(safe) > max_chars else safe

    return {
        'system': _trim(prompt.system or ''),
        'messages': [
            {'role': m.role.value, 'content': _trim(m.content)}
            for m in prompt.messages
        ],
    }
