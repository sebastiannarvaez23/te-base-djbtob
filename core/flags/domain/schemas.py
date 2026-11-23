"""Base FlagContext — portable fields from necore + geo resolution via location helpers."""
from __future__ import annotations

from typing import Optional

from necore.flags.domain.schemas import (  # noqa: F401
    FlagDefinition,
    FlagScope,
    _empty_to_none,
)
from necore.flags.domain.schemas import FlagContext as _FlagContext


class FlagContext(_FlagContext):
    @classmethod
    def from_request(cls, request) -> FlagContext:
        company = getattr(request, 'tenant', None)
        user = getattr(request, 'user', None)

        company_id = country = state = city = None
        if company is not None:
            raw_id = getattr(company, 'id', None)
            company_id = _empty_to_none(str(raw_id) if raw_id is not None else None)
            from core.location import entity_location_labels

            country_name, state_name, city_name = entity_location_labels(company)
            country = _empty_to_none(country_name)
            state = _empty_to_none(state_name)
            city = _empty_to_none(city_name)

        user_id = None
        if user is not None and getattr(user, 'is_authenticated', False):
            raw_uid = getattr(user, 'id', None)
            if raw_uid is not None:
                user_id = _empty_to_none(str(raw_uid))

        return cls(
            company_id=company_id,
            user_id=user_id,
            country=country,
            state=state,
            city=city,
        )


__all__ = ['FlagContext', 'FlagDefinition', 'FlagScope', '_empty_to_none']
