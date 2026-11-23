"""Pydantic contracts — currency catalog."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_CURRENCY_RE = re.compile(r'^[A-Z]{3}$')
_COUNTRY_RE = re.compile(r'^[A-Z]{2}$')


def normalize_currency_code(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _CURRENCY_RE.match(cleaned):
        raise ValueError('currency code must be ISO 4217 alpha-3 (e.g. USD)')
    return cleaned


def normalize_country_code(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _COUNTRY_RE.match(cleaned):
        raise ValueError('country code must be ISO 3166-1 alpha-2 (e.g. CO)')
    return cleaned


def normalize_name(value: str) -> str:
    cleaned = (value or '').strip()
    if not cleaned:
        raise ValueError('name must not be blank')
    return cleaned


class CurrencySchema(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    decimal_places: int = 2
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateCurrencySchema(BaseModel):
    code: str
    name: str
    decimal_places: int = 2
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_currency_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator('decimal_places')
    @classmethod
    def _decimals(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError('decimal_places must be between 0 and 6')
        return value


class UpdateCurrencySchema(BaseModel):
    name: Optional[str] = None
    decimal_places: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_name(value)

    @field_validator('decimal_places')
    @classmethod
    def _decimals(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 0 or value > 6:
            raise ValueError('decimal_places must be between 0 and 6')
        return value


class CountryCurrencySchema(BaseModel):
    id: uuid.UUID
    country_id: uuid.UUID
    country_code: str = ''
    currency_id: uuid.UUID
    currency_code: str = ''
    currency_name: str = ''
    decimal_places: int = 2
    is_default: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateCountryCurrencySchema(BaseModel):
    country_id: uuid.UUID
    currency_id: uuid.UUID
    is_default: bool = False
    is_active: bool = True


class UpdateCountryCurrencySchema(BaseModel):
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class AllowedCurrencySchema(BaseModel):
    """Lean projection for charge UI / policy lookups."""

    code: str
    name: str
    decimal_places: int = 2
    is_default: bool = False


class UpsertCurrencySeedSchema(BaseModel):
    code: str
    name: str
    decimal_places: int = 2

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_currency_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_name(value)
