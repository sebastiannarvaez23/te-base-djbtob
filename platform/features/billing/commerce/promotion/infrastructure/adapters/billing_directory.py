"""Billing directory adapter — admin email / company name for promo emails."""

import uuid
from typing import Optional

from platform.features.billing.common.directory import DjangoBillingDirectory
from platform.features.billing.commerce.promotion.domain.interfaces import IBillingDirectoryPort
from platform.features.billing.commerce.promotion.domain.schemas import AdminSnapshot


class DjangoPromoBillingDirectory(IBillingDirectoryPort):

    def __init__(self, directory=None):
        self._directory = directory or DjangoBillingDirectory()

    def admin_of(self, company_id: uuid.UUID) -> Optional[AdminSnapshot]:
        admin = self._directory.admin_of(company_id)
        if admin is None or not getattr(admin, 'email', ''):
            return None
        return AdminSnapshot(
            email=admin.email,
            first_name=getattr(admin, 'first_name', '') or '',
            last_name=getattr(admin, 'last_name', '') or '',
        )

    def company_name(self, company_id: uuid.UUID) -> str:
        company = self._directory.company(company_id)
        return getattr(company, 'name', '') or '' if company is not None else ''
