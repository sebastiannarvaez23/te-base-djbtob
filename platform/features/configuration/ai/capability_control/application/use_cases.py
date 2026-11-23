from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from core.ai.health import RuntimeHealthProbe
from core.errors import ValidationAppException
from core.errors.codes import AppErrorCode
from core.trace import trace_layer

from platform.features.configuration.ai.capability_control.domain.interfaces import (
    ICapabilityControlRepository,
)
from platform.features.configuration.ai.capability_control.domain.schemas import (
    CONTROL_CAPABILITIES,
    CapabilityControlAdminSchema,
    CapabilityStubSchema,
    default_capabilities,
)


class GetCapabilityControlUseCase:
    def __init__(
        self,
        repository: ICapabilityControlRepository,
        health: RuntimeHealthProbe | None = None,
    ):
        self.repository = repository
        self.health = health or RuntimeHealthProbe()

    @trace_layer('application')
    def execute(self) -> CapabilityControlAdminSchema:
        items = self.repository.get_all() or default_capabilities()
        by_key = {i.key: i for i in items}
        merged = []
        for key in CONTROL_CAPABILITIES:
            stub = by_key.get(key) or CapabilityStubSchema(key=key)
            merged.append(stub.model_copy(update={
                'runtime_health': self.health.probe(stub.provider),
            }))
        return CapabilityControlAdminSchema(
            capabilities=merged,
            updated_at=self.repository.get_updated_at(),
        )


class UpdateCapabilityControlUseCase:
    def __init__(
        self,
        repository: ICapabilityControlRepository,
        health: RuntimeHealthProbe | None = None,
    ):
        self.repository = repository
        self.health = health or RuntimeHealthProbe()

    @trace_layer('application')
    def execute(self, body: dict) -> CapabilityControlAdminSchema:
        raw = body.get('capabilities') or []
        if len(raw) != len(CONTROL_CAPABILITIES):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='capabilities must include the full control catalog.',
            )
        try:
            items = [CapabilityStubSchema.model_validate(item) for item in raw]
        except PydanticValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=str(exc.errors()),
            ) from exc
        keys = {i.key for i in items}
        if keys != set(CONTROL_CAPABILITIES):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='capabilities catalog mismatch.',
            )
        self.repository.save_all(items)
        return GetCapabilityControlUseCase(self.repository, self.health).execute()
