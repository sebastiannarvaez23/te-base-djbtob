import uuid
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubscriptionModuleSchema(BaseModel):
    id: int
    subscription_id: uuid.UUID
    subscription_name: str
    module_code: str

    model_config = {"from_attributes": True}


class UpdateSubscriptionModulesSchema(BaseModel):
    module_codes: list[str] = []
