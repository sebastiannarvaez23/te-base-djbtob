"""ConflictResolver — el sistema local gana en campos críticos."""

from __future__ import annotations

from typing import Any, Iterable

from core.integrations.domain.schemas import ConflictResolution


class ConflictResolver:
    """
    Resuelve divergencias entre el payload inbound y el estado local.

    Política fija: el sistema local gana en campos críticos.
    ``warehouse_id`` no forma parte de los campos críticos por defecto.
    """

    def resolve(
        self,
        inbound: dict[str, Any],
        current_wms: dict[str, Any],
        *,
        critical_fields: Iterable[str] | None = None,
    ) -> list[ConflictResolution]:
        fields = list(critical_fields or ('status', 'quantity'))
        resolutions: list[ConflictResolution] = []

        for field in fields:
            if field not in inbound:
                continue
            inbound_val = inbound.get(field)
            wms_val = current_wms.get(field)
            if inbound_val != wms_val and field in current_wms:
                resolutions.append(
                    ConflictResolution(
                        kept='wms',
                        field=field,
                        inbound_value=inbound_val,
                        wms_value=wms_val,
                        warning=(
                            f'Field "{field}" conflict: inbound={inbound_val!r} '
                            f'discarded in favor of WMS value {wms_val!r}'
                        ),
                    )
                )
        return resolutions

    def apply_wms_wins(
        self,
        inbound: dict[str, Any],
        current_wms: dict[str, Any],
        *,
        critical_fields: Iterable[str] | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        """Devuelve payload merged (WMS gana en conflictos) y lista de warnings."""
        merged = dict(inbound)
        warnings: list[str] = []
        for resolution in self.resolve(inbound, current_wms, critical_fields=critical_fields):
            merged[resolution.field] = resolution.wms_value
            warnings.append(resolution.warning)
        return merged, warnings
