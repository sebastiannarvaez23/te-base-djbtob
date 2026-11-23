from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError as PydanticValidationError

from core.ai.health import RuntimeHealthProbe
from core.ai.model_layer.budget import BudgetGuard
from core.ai.model_layer.catalog import AI_CAPABILITIES
from core.errors import ValidationAppException
from core.errors.codes import AppErrorCode
from core.trace import trace_layer

from platform.features.configuration.ai.model_routing.domain.interfaces import IModelRoutingRepository
from platform.features.configuration.ai.model_routing.domain.schemas import (
    ModelRoutingAdminSchema,
    admin_routes_to_table,
    table_to_admin_routes,
)


class GetModelRoutingAdminUseCase:
    def __init__(self, repository: IModelRoutingRepository, health: RuntimeHealthProbe | None = None):
        self.repository = repository
        self.health = health or RuntimeHealthProbe()

    @trace_layer('application')
    def execute(self) -> ModelRoutingAdminSchema:
        table = self.repository.get_table()
        providers = {r.provider for r in table.routes.values()}
        health_map = {p: self.health.probe(p) for p in providers}
        spent = BudgetGuard(hourly_budget_usd=table.hourly_budget_usd).spent_usd()
        return ModelRoutingAdminSchema(
            routes=table_to_admin_routes(table, health_by_provider=health_map),
            hourly_budget_usd=table.hourly_budget_usd,
            spent_usd_window=spent,
            updated_at=self.repository.get_updated_at(),
        )


class UpdateModelRoutingAdminUseCase:
    def __init__(self, repository: IModelRoutingRepository, health: RuntimeHealthProbe | None = None):
        self.repository = repository
        self.health = health or RuntimeHealthProbe()

    @trace_layer('application')
    def execute(self, body: dict) -> ModelRoutingAdminSchema:
        routes = body.get('routes') or []
        if len(routes) != len(AI_CAPABILITIES):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='routes must include every AI capability.',
            )
        seen = set()
        for item in routes:
            cap = (item.get('capability') or '').lower().strip()
            if cap in seen:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail=f'Duplicate capability: {cap}',
                )
            seen.add(cap)
        if seen != set(AI_CAPABILITIES):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='routes must cover the full capability catalog.',
            )
        budget_raw = body.get('hourly_budget_usd', None)
        budget = Decimal(str(budget_raw)) if budget_raw not in (None, '') else None
        try:
            table = admin_routes_to_table(routes, hourly_budget_usd=budget)
        except PydanticValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=str(exc.errors()),
            ) from exc
        self.repository.save_table(table)
        return GetModelRoutingAdminUseCase(self.repository, self.health).execute()
