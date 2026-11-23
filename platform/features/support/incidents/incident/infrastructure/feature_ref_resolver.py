"""DjangoFeatureRefResolver — adapta el catálogo de funcionalidades al puerto."""

from __future__ import annotations

import logging

from platform.features.support.incidents.incident.domain.interfaces import IFeatureRefResolver

logger = logging.getLogger('app.api')


class DjangoFeatureRefResolver(IFeatureRefResolver):

    def resolve(self, feature_key: str) -> tuple[str, str]:
        key = (feature_key or '').strip()
        if not key:
            return '', ''
        try:
            from platform.features.security.access.functionalities.models import Functionality
            row = (
                Functionality.objects.filter(key=key, is_active=True)
                .values_list('module_id', 'id')
                .first()
            )
        except Exception as exc:
            logger.warning(
                'MANUAL_INCIDENT_FEATURE_RESOLVE_FAILED key=%s error=%s',
                key, exc,
            )
            return '', ''
        if not row:
            logger.warning('MANUAL_INCIDENT_FEATURE_MISSING key=%s', key)
            return '', ''
        return str(row[0] or ''), str(row[1] or '')
