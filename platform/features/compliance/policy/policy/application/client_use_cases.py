"""Casos de uso orientados al mundo client (audiencia tenant)."""

from __future__ import annotations

import uuid

from core.errors import AppErrorCode, NotFoundException
from core.storage import IStorageService

from ..domain.enums import PolicyAudience
from ..domain.interfaces import IPolicyRepository
from ..domain.schemas import PolicyCountryContentSchema, PolicySchema
from .use_cases import GetPolicyCountryContentUseCase
from core.trace import trace_layer


class RequireActiveClientPolicyUseCase:
    """Resuelve una política activa de audiencia client; 404 si no aplica."""

    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID) -> PolicySchema:
        policy = self.repository.get_by_id(policy_id)
        if (
            not policy
            or policy.audience != PolicyAudience.CLIENT
            or not policy.is_active
        ):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return policy


class GetClientPolicyCountryContentUseCase:
    """Markdown de una política client activa (oculta políticas admin)."""

    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, country: str) -> PolicyCountryContentSchema:
        RequireActiveClientPolicyUseCase(self.repository).execute(policy_id)
        return GetPolicyCountryContentUseCase(self.repository, self.storage).execute(
            policy_id, country,
        )
