from typing import Iterable
from uuid import UUID

from client.features.security.access.entity_grants.domain.interfaces import ICompanyUserDirectory
from client.features.security.lifecycle.registration.models import User


class DjangoCompanyUserDirectory(ICompanyUserDirectory):

    def member_ids(self, company_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        return set(
            User.objects.filter(company_id=company_id, id__in=list(ids)).values_list('id', flat=True),
        )
