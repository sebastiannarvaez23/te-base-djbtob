"""Resolves the platform's billing company used for public voucher purchases."""

import uuid

from django.conf import settings

from core.errors import AppErrorCode, AppException

from platform.features.billing.commerce.promotion.domain.interfaces import IBillingCompanyPort


class DjangoBillingCompany(IBillingCompanyPort):

    def resolve_public_billing_company_id(self) -> uuid.UUID:
        configured = getattr(settings, 'PROMO_PUBLIC_BILLING_COMPANY_ID', None)
        if configured:
            return uuid.UUID(str(configured))
        from platform.features.company.tenant.company.models import Company
        company = Company.objects.order_by('created').first()
        if company is None:
            raise AppException(AppErrorCode.PROMO_INTERNAL)
        return company.id
