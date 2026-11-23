"""
SystemVarsBuilder — builds the runtime-injected variables for a render.

System vars override nothing in user-provided data, but are merged into
the template context so {{ uuid }}, {{ timestamp }}, {{ year }} etc. are
always available regardless of what the admin put in mock_data.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from core.ids import uuid7

from ...domain.enums import DocumentFormat, FORMAT_EXTENSIONS


class SystemVarsBuilder:

    def build(
        self,
        format: DocumentFormat,
        user=None,
        tenant=None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        vars: dict[str, Any] = {
            'uuid':          str(uuid7()),
            'timestamp':     int(now.timestamp() * 1000),
            'iso_timestamp': now.isoformat(),
            'year':          f'{now.year:04d}',
            'month':         f'{now.month:02d}',
            'day':           f'{now.day:02d}',
            'ext':           FORMAT_EXTENSIONS[format],
        }

        if user is not None:
            user_id = getattr(user, 'id', None) or getattr(user, 'pk', None)
            if user_id is not None:
                vars['user_id'] = str(user_id)

        if tenant is not None:
            tenant_code = getattr(tenant, 'code', None) or getattr(tenant, 'schema_name', None)
            if tenant_code:
                vars['tenant_code'] = str(tenant_code)

        if extra:
            vars.update(extra)

        return vars
