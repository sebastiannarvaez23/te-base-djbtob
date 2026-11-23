"""Schemas Pydantic para resultados de reconciliación de cupos activos."""

from pydantic import BaseModel, Field


class FeatureQuotaReconcileSchema(BaseModel):
    feature_key: str
    max_value: int
    active_before: int
    deactivated_count: int
    deactivated_ids: list[str] = Field(default_factory=list)
    incomplete: bool = False


class CompanyQuotaReconcileSchema(BaseModel):
    company_id: str
    subscription_id: str
    features: list[FeatureQuotaReconcileSchema] = Field(default_factory=list)
