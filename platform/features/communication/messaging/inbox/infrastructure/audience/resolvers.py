"""Resolución de audiencia (Strategy + Registry).

Cada estrategia traduce una ``Audience`` a una lista de ``RecipientGroup``
(destinatarios agrupados por schema de tenant), consultando los modelos
públicos ``User`` y ``Company``. Agregar un nuevo alcance es agregar una
estrategia y registrarla — sin tocar las existentes (OCP).
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from django.contrib.auth import get_user_model

from platform.features.company.tenant.company.models import Company
from platform.features.communication.messaging.inbox.domain.enums import AudienceScope
from platform.features.communication.messaging.inbox.domain.interfaces import IAudienceResolver
from platform.features.communication.messaging.inbox.domain.schemas import Audience, RecipientGroup

User = get_user_model()


def _active_user_ids(company_id) -> list:
    return list(
        User.objects.filter(company_id=company_id, is_active=True)
        .values_list('id', flat=True)
    )


# ── Estrategias por alcance ───────────────────────────────────────────────────

class _ScopeStrategy(ABC):
    @abstractmethod
    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        ...


class SingleUserStrategy(_ScopeStrategy):
    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        try:
            user = User.objects.select_related('company').get(
                id=audience.target_user_id, is_active=True,
            )
        except User.DoesNotExist:
            return []
        return [RecipientGroup(schema_name=user.company.schema_name, user_ids=[user.id])]


class CompanyUsersStrategy(_ScopeStrategy):
    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        try:
            company = Company.objects.get(id=audience.target_company_id)
        except Company.DoesNotExist:
            return []
        user_ids = _active_user_ids(company.id)
        if not user_ids:
            return []
        return [RecipientGroup(schema_name=company.schema_name, user_ids=user_ids)]


class AllTenantsStrategy(_ScopeStrategy):
    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        # Mapa company_id → schema (una sola query), excluyendo el público.
        schema_by_company: Dict = {
            c.id: c.schema_name
            for c in Company.objects.exclude(schema_name='public')
        }
        # Agrupa los usuarios activos por empresa en una sola pasada.
        ids_by_company: Dict[object, list] = {}
        for uid, company_id in User.objects.filter(
            is_active=True, company_id__in=schema_by_company.keys(),
        ).values_list('id', 'company_id'):
            ids_by_company.setdefault(company_id, []).append(uid)

        return [
            RecipientGroup(schema_name=schema_by_company[company_id], user_ids=ids)
            for company_id, ids in ids_by_company.items()
            if ids
        ]


# ── Registry (implementa el puerto IAudienceResolver) ─────────────────────────

class AudienceResolverRegistry(IAudienceResolver):
    """Selecciona la estrategia según el alcance y delega la resolución."""

    def __init__(self, strategies: Dict[AudienceScope, _ScopeStrategy]):
        self._strategies = strategies

    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        strategy = self._strategies.get(audience.scope)
        if strategy is None:
            return []
        return strategy.resolve(audience)

    @classmethod
    def default(cls) -> 'AudienceResolverRegistry':
        return cls({
            AudienceScope.SINGLE_USER: SingleUserStrategy(),
            AudienceScope.COMPANY_USERS: CompanyUsersStrategy(),
            AudienceScope.ALL_TENANTS: AllTenantsStrategy(),
        })
