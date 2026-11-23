"""Casos de uso públicos: solo versión publicada (firmable) por código."""

from __future__ import annotations

from core.errors import AppErrorCode, NotFoundException
from core.storage import IStorageService

from ..domain.enums import PolicyAudience, PolicyCountryStatus
from ..domain.interfaces import IPolicyRepository
from ..domain.schemas import PolicyCountryContentSchema, normalize_code, normalize_country
from .use_cases import GetPolicyCountryContentUseCase
from core.trace import trace_layer


class GetPublishedPolicyByCodeUseCase:
    """Devuelve el markdown de la única versión *published* de un código.

    No expone drafts, approved ni revoked. Al liberar una versión nueva,
    ``release_approved_version`` depreca automáticamente la publicada previa.
    """

    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(
        self,
        code: str,
        country: str,
        *,
        audience: PolicyAudience = PolicyAudience.CLIENT,
    ) -> PolicyCountryContentSchema:
        try:
            code = normalize_code(code)
            country = normalize_country(country)
        except ValueError as exc:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND) from exc

        policy = self.repository.get_by_code(code)
        if (
            not policy
            or not policy.is_active
            or policy.audience != audience
        ):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        content = GetPolicyCountryContentUseCase(self.repository, self.storage).execute(
            policy.id, country,
        )
        if content.status != PolicyCountryStatus.PUBLISHED:
            raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)
        return content
