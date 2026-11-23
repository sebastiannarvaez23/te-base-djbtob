from django.conf import settings

from platform.features.billing.commerce.invoice.domain.fiscal import IFiscalInvoicingProvider
from platform.features.billing.commerce.invoice.infrastructure.fiscal.local import (
    LocalFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.neurana import (
    NeuranaFiscalInvoicingProvider,
)


def get_fiscal_invoicing_provider() -> IFiscalInvoicingProvider:
    provider = (getattr(settings, 'INVOICING_PROVIDER', 'local') or 'local').strip().lower()
    if provider == 'neurana' and getattr(settings, 'NE_ECOSYSTEM_ENABLED', False):
        return NeuranaFiscalInvoicingProvider()
    return LocalFiscalInvoicingProvider()
