"""
Contexto de navegación WMS por request.

El navegador es la fuente de verdad. El cliente envía un header compacto
``X-UI-Context`` en cada llamada API. ``CatalogAccessMiddleware`` usa
``mc`` / ``mid`` para denegar módulos/secciones inactivos; el resto
etiqueta incidencias. No se persiste en caliente.
"""

import re
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

HEADER_NAME = 'HTTP_X_UI_CONTEXT'
MAX_HEADER_LEN = 220

_FEATURE_RE = re.compile(r'^[a-z][a-z0-9._-]{0,99}$')
_SECTION_RE = re.compile(r'^[a-z0-9._-]{1,63}$')
_MODULE_CODE_RE = re.compile(r'^[A-Za-z0-9_.\-]{1,100}$')
_TOKEN_RE = re.compile(r'^[a-z][a-z0-9_]{0,15}=[A-Za-z0-9._-]{0,100}$')


@dataclass(frozen=True)
class UiContext:
    module_id: str = ''
    module_code: str = ''
    functionality_id: str = ''
    page_section: str = ''
    feature_key: str = ''


_current_ui: ContextVar[UiContext] = ContextVar('ui_context', default=UiContext())


def set_ui_context(ctx: UiContext) -> None:
    _current_ui.set(ctx)


def reset_ui_context() -> None:
    _current_ui.set(UiContext())


def get_ui_context() -> UiContext:
    return _current_ui.get()


def ui_context_dict() -> dict:
    ctx = get_ui_context()
    return {
        'module_id': ctx.module_id,
        'module_code': ctx.module_code,
        'functionality_id': ctx.functionality_id,
        'page_section': ctx.page_section,
        'feature_key': ctx.feature_key,
    }


def ui_context_from_request(request) -> UiContext:
    """Lee ``X-UI-Context`` del request. Header inválido → contexto vacío."""
    meta = getattr(request, 'META', None) or {}
    raw = meta.get(HEADER_NAME) or ''
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ''
    return parse_ui_context_header(str(raw))


def parse_ui_context_header(raw: str) -> UiContext:
    """Parsea ``fk=...;ps=...;mid=...;mc=...``. Partes inválidas se ignoran."""
    text = (raw or '').strip()[:MAX_HEADER_LEN]
    if not text:
        return UiContext()

    feature_key = ''
    page_section = ''
    module_id = ''
    module_code = ''

    for part in text.split(';'):
        token = part.strip()
        if not token or '=' not in token:
            continue
        if not _TOKEN_RE.match(token):
            continue
        key, _, value = token.partition('=')
        value = value.strip()
        if key == 'fk' and _FEATURE_RE.match(value):
            feature_key = value
        elif key == 'ps' and _SECTION_RE.match(value):
            page_section = value
        elif key == 'mid' and _is_uuid(value):
            module_id = value.lower()
        elif key == 'mc' and _MODULE_CODE_RE.match(value):
            module_code = value

    if not feature_key and not page_section and not module_id and not module_code:
        return UiContext()
    return UiContext(
        module_id=module_id,
        module_code=module_code,
        page_section=page_section,
        feature_key=feature_key,
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
