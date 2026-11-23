"""
PathResolver — resolves a template's storage_path_template to a real,
safe object key inside MinIO.

Order of operations:
  1. Interpolate placeholders using the canonical TemplateEngine.
  2. Sanitize each path segment (drop control chars, illegal characters).
  3. Reject any traversal attempt (.., leading /, double //, empty segments).
  4. Reject results that still contain Jinja markers (a placeholder didn't
     resolve, which means the template would collide across documents).

Returns the resolved object key (no leading slash). The caller chooses
the bucket separately (template.storage_bucket or settings default).
"""
import re
from typing import Any

from core.errors import AppErrorCode, AppException

from ...domain.template_engine import ITemplateEngine
from ...domain.schemas import DocumentTemplateSchema


_ILLEGAL_SEGMENT_CHARS_RE = re.compile(r'[\\:\*\?"<>\|]')
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x1f\x7f]')
_LEFTOVER_PLACEHOLDER_RE = re.compile(r'\{\{|\}\}|\{%|%\}')
_VAR_SEGMENT_RE = re.compile(r'^\{\{\s*(\w+)\s*\}\}$')


def extract_path_variable(path_template: str, object_key: str, variable: str) -> str | None:
    """Return the object-key segment that filled ``variable`` in the path template.

    Only handles variables that occupy a whole path segment, e.g.
    ``admin/{{ tenant_code }}/file.pdf``. Returns ``None`` when the
    template does not declare the variable as its own segment or the key
    is too short to align.
    """
    if not path_template or not object_key:
        return None

    tpl_parts = [p for p in path_template.strip('/').split('/') if p]
    key_parts = [p for p in object_key.strip('/').split('/') if p]

    if len(key_parts) != len(tpl_parts):
        return None

    for i, part in enumerate(tpl_parts):
        match = _VAR_SEGMENT_RE.match(part.strip())
        if match:
            if match.group(1) == variable:
                return key_parts[i]
            continue
        if key_parts[i] != part.strip():
            return None

    return None


_PLACEHOLDER_START_RE = re.compile(r'\{\{|\{%')


def extract_static_prefix(path_template: str) -> str:
    """Return the longest path prefix that contains no placeholders.

    Used to narrow MinIO listings for a template. For example:
      "facturas/{{ year }}/INV-{{ uuid }}.pdf" → "facturas/"
      "{{ kind }}/{{ year }}/..."              → ""

    The result always ends at a `/` boundary (we don't keep partial
    segments). Returns "" when no static prefix exists.
    """
    if not path_template:
        return ''

    match = _PLACEHOLDER_START_RE.search(path_template)
    head = path_template if match is None else path_template[: match.start()]

    slash = head.rfind('/')
    if slash < 0:
        return ''
    return head[: slash + 1].lstrip('/')


class PathResolver:

    def __init__(self, engine: ITemplateEngine):
        self._engine = engine

    def resolve(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> str:
        raw = (template.storage_path_template or '').strip()
        if not raw:
            raise AppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail='Template has no storage_path_template.',
            )

        # Strict mode: a missing variable in a path would silently
        # collapse to "" and produce collisions (e.g. facturas//x.pdf).
        # We force the engine to raise instead, then re-raise as a path
        # error so the caller gets the right contextual code.
        try:
            interpolated = self._engine.interpolate_strict(raw, data, system_vars)
        except AppException as exc:
            raise AppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail=(
                    f'Path template "{raw}" references variables that are not '
                    f'provided in data or system_vars: {exc.detail}'
                ),
            )

        if _LEFTOVER_PLACEHOLDER_RE.search(interpolated):
            raise AppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail=(
                    f'Path template still contains unresolved placeholders after '
                    f'interpolation: "{interpolated}". Provide values for all '
                    f'variables used in storage_path_template.'
                ),
            )

        cleaned = self._sanitize(interpolated)
        self._validate_no_traversal(cleaned)
        return cleaned

    def _sanitize(self, path: str) -> str:
        # Drop control chars anywhere.
        path = _CONTROL_CHARS_RE.sub('', path)
        # Strip surrounding slashes — object keys never start with '/'.
        path = path.strip('/').strip()

        segments = []
        for raw_seg in path.split('/'):
            seg = raw_seg.strip()
            if not seg:
                continue
            seg = _ILLEGAL_SEGMENT_CHARS_RE.sub('_', seg)
            segments.append(seg)

        return '/'.join(segments)

    def _validate_no_traversal(self, path: str) -> None:
        if not path:
            raise AppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail='Resolved storage path is empty after sanitization.',
            )

        for seg in path.split('/'):
            if seg in ('.', '..'):
                raise AppException(
                    AppErrorCode.DOC_STORAGE_PATH_INVALID,
                    override_detail=f'Resolved storage path contains traversal segment "{seg}".',
                )
