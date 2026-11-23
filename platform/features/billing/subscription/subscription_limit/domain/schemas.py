import uuid
from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import datetime

from .window import VALIDATION_TYPES, resolved_window_hours


class SubscriptionLimitSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    subscription_id: uuid.UUID
    functionality_id: uuid.UUID
    subscription_name: str
    functionality_key: str
    functionality_label: str
    functionality_module_code: str
    name: str = ''
    max_value: int
    validation_type: str = 'lifetime'
    window_hours: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateSubscriptionLimitSchema(BaseModel):
    subscription_id: uuid.UUID
    functionality_id: uuid.UUID
    name: str = ''
    max_value: int
    validation_type: str = 'lifetime'
    window_hours: Optional[int] = None

    @model_validator(mode='after')
    def _window_invariant(self):
        if self.validation_type not in VALIDATION_TYPES:
            raise ValueError(f'Invalid validation_type: {self.validation_type}')
        self.window_hours = resolved_window_hours(
            self.validation_type,
            self.window_hours,
            require_if_window=True,
        )
        return self


class UpdateSubscriptionLimitSchema(BaseModel):
    name: Optional[str] = None
    max_value: Optional[int] = None
    validation_type: Optional[str] = None
    window_hours: Optional[int] = None

    @model_validator(mode='after')
    def _window_invariant(self):
        if self.validation_type is not None and self.validation_type not in VALIDATION_TYPES:
            raise ValueError(f'Invalid validation_type: {self.validation_type}')
        if self.validation_type in ('daily', 'lifetime'):
            self.window_hours = None
        elif self.validation_type == 'window' and self.window_hours is not None:
            self.window_hours = resolved_window_hours(
                'window', self.window_hours, require_if_window=True,
            )
        elif self.window_hours is not None and self.validation_type is None:
            # Solo hours en el patch: rango válido; el use case resuelve el tipo.
            self.window_hours = resolved_window_hours(
                'window', self.window_hours, require_if_window=True,
            )
        return self
