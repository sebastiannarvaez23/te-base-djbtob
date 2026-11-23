"""Extractor incremental del campo ``text`` en JSON ``action=final`` del SLM."""

from __future__ import annotations

import re
from typing import List


_ACTION_FINAL_RE = re.compile(
    r'"action"\s*:\s*"final"',
    re.IGNORECASE,
)
_TEXT_KEY_RE = re.compile(
    r'"text"\s*:\s*"',
)


class FinalTextStreamExtractor:
    """
    Observa el buffer JSON que produce el modelo y, cuando detecta
    ``{"action":"final", ..., "text":"..."}``, emite los caracteres del
    valor ``text`` a medida que llegan (respetando escapes JSON).
    """

    def __init__(self):
        self._buf = ''
        self._phase = 'seek_action'  # seek_action | seek_text | in_text | done
        self._escape = False
        self._emitted = ''
        self._saw_final_action = False

    @property
    def emitted_text(self) -> str:
        return self._emitted

    @property
    def is_done(self) -> bool:
        return self._phase == 'done'

    @property
    def saw_final_action(self) -> bool:
        return self._saw_final_action

    def feed(self, chunk: str) -> List[str]:
        if not chunk or self._phase == 'done':
            return []
        self._buf += chunk
        out: List[str] = []

        if self._phase == 'seek_action':
            if _ACTION_FINAL_RE.search(self._buf):
                self._saw_final_action = True
                self._phase = 'seek_text'
            else:
                # Si ya es obvio que es tool, no tiene sentido seguir buscando text.
                if re.search(r'"action"\s*:\s*"tool"', self._buf, re.IGNORECASE):
                    return []
                return []

        if self._phase == 'seek_text':
            match = _TEXT_KEY_RE.search(self._buf)
            if not match:
                return []
            # Continuar desde el primer carácter del valor string.
            self._buf = self._buf[match.end():]
            self._phase = 'in_text'

        if self._phase == 'in_text':
            i = 0
            data = self._buf
            while i < len(data):
                ch = data[i]
                if self._escape:
                    mapped = {
                        '"': '"',
                        '\\': '\\',
                        '/': '/',
                        'b': '\b',
                        'f': '\f',
                        'n': '\n',
                        'r': '\r',
                        't': '\t',
                    }.get(ch, ch)
                    out.append(mapped)
                    self._emitted += mapped
                    self._escape = False
                    i += 1
                    continue
                if ch == '\\':
                    self._escape = True
                    i += 1
                    continue
                if ch == '"':
                    self._phase = 'done'
                    i += 1
                    break
                out.append(ch)
                self._emitted += ch
                i += 1
            self._buf = data[i:]

        return out

    def remaining_from(self, final_text: str) -> str:
        """Si el parse completo tiene más texto del emitido, devolver el resto."""
        final = final_text or ''
        emitted = self._emitted
        if not emitted:
            return final
        if final.startswith(emitted):
            return final[len(emitted):]
        # Desync: reenviar todo el final (el cliente puede haber visto basura parcial).
        return final
