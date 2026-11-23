import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from platform.features.configuration.landing.landing.domain.catalog import LANDING_SECTION_KEYS


class LandingSectionSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    key: str
    is_visible: bool = True
    sort_order: int = 0
    label_es: str = ''
    label_en: str = ''
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class ToggleLandingSectionSchema(BaseModel):
    is_visible: bool

    @field_validator('is_visible')
    @classmethod
    def require_bool(cls, v: bool) -> bool:
        return bool(v)


class PublicLandingSectionsSchema(BaseModel):
    """Narrow public projection for base-landing-web."""

    sections: dict[str, bool]


def assert_known_key(key: str) -> str:
    if key not in LANDING_SECTION_KEYS:
        raise ValueError(f'Unknown landing section key: {key!r}')
    return key
