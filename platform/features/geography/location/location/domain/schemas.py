"""Contratos Pydantic — maestra geográfica."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

_COUNTRY_RE = re.compile(r'^[A-Z]{2}$')
_CODE_RE = re.compile(r'^[A-Z0-9][A-Z0-9\-_]{0,19}$')


def normalize_country_code(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _COUNTRY_RE.match(cleaned):
        raise ValueError('country code must be ISO 3166-1 alpha-2 (e.g. CO)')
    return cleaned


def normalize_location_code(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _CODE_RE.match(cleaned):
        raise ValueError('code must be alphanumeric (e.g. ANT or 05001)')
    return cleaned


def normalize_name(value: str) -> str:
    cleaned = (value or '').strip()
    if not cleaned:
        raise ValueError('name must not be blank')
    return cleaned


def normalize_coord(value: Optional[Decimal], *, kind: str) -> Optional[Decimal]:
    if value is None:
        return None
    if kind == 'lat' and not (Decimal('-90') <= value <= Decimal('90')):
        raise ValueError('latitude must be between -90 and 90')
    if kind == 'lng' and not (Decimal('-180') <= value <= Decimal('180')):
        raise ValueError('longitude must be between -180 and 180')
    return value


class CountrySchema(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateCountrySchema(BaseModel):
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_country_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class UpdateCountrySchema(BaseModel):
    name: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class DepartmentSchema(BaseModel):
    id: uuid.UUID
    country_id: uuid.UUID
    country_code: str = ''
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateDepartmentSchema(BaseModel):
    country_id: uuid.UUID
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_location_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class UpdateDepartmentSchema(BaseModel):
    name: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class CitySchema(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    department_code: str = ''
    country_id: Optional[uuid.UUID] = None
    country_code: str = ''
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateCitySchema(BaseModel):
    department_id: uuid.UUID
    code: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_location_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class UpdateCitySchema(BaseModel):
    name: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_name(value)

    @field_validator('latitude')
    @classmethod
    def _lat(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lat')

    @field_validator('longitude')
    @classmethod
    def _lng(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        return normalize_coord(value, kind='lng')


class LocationImportRowError(BaseModel):
    row: int
    field: str = ''
    code: str
    detail: str


class LocationImportResultSchema(BaseModel):
    created_countries: int = 0
    updated_countries: int = 0
    created_departments: int = 0
    updated_departments: int = 0
    created_cities: int = 0
    updated_cities: int = 0
    skipped: int = 0
    errors: List[LocationImportRowError] = Field(default_factory=list)
