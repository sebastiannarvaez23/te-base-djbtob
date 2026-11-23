"""Parseo del protocolo JSON tool/final (apto para SLM pequeño)."""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, Literal, Optional

from pydantic import BaseModel, Field


class ParsedAgentAction(BaseModel):
    """Acción parseada de la salida del modelo (contrato harness)."""

    action: Literal['tool', 'final']
    name: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    text: Optional[str] = None


_TOKEN_CHUNK = 10


def extract_first_json_object(text: str) -> Optional[str]:
    """Return the first brace-balanced JSON object, respecting string escapes."""
    start = text.find('{')
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_str:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def parse_agent_action(raw: str) -> Optional[ParsedAgentAction]:
    text = (raw or '').strip()
    if not text:
        return None
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        extracted = extract_first_json_object(text)
        if not extracted:
            return ParsedAgentAction(action='final', text=text)
        try:
            data = json.loads(extracted)
        except json.JSONDecodeError:
            return ParsedAgentAction(action='final', text=text)

    if not isinstance(data, dict):
        return ParsedAgentAction(action='final', text=text)

    action = str(data.get('action') or '').lower()
    if action == 'tool':
        name = str(data.get('name') or '').strip()
        if not name:
            return None
        args = data.get('arguments') or data.get('args') or {}
        if not isinstance(args, dict):
            args = {}
        return ParsedAgentAction(action='tool', name=name, arguments=args)
    if action == 'final':
        return ParsedAgentAction(
            action='final',
            text=str(data.get('text') or '').strip() or text,
        )
    if 'text' in data:
        return ParsedAgentAction(action='final', text=str(data.get('text') or ''))
    return ParsedAgentAction(action='final', text=text)


def chunk_text(text: str, size: int = _TOKEN_CHUNK) -> Iterator[str]:
    """Parte la respuesta final en trozos (fallback si no hubo stream nativo)."""
    if not text:
        return
    step = max(1, size)
    for i in range(0, len(text), step):
        yield text[i:i + step]
