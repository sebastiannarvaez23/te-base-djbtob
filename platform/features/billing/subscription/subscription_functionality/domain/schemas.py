import uuid
from pydantic import BaseModel
from typing import Optional


class SubscriptionFunctionalitySchema(BaseModel):
    id: int
    subscription_id: uuid.UUID
    subscription_name: str
    functionality_key: str
    functionality_label: str
    functionality_module_code: str

    model_config = {"from_attributes": True}


class UpdateSubscriptionFunctionalitiesSchema(BaseModel):
    functionality_keys: list[str] = []
