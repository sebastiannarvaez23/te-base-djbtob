"""
Shared charge helper for subscription plan billing.

Three flows charge a plan — upgrade (``ChangeSubscriptionUseCase``), scheduled
downgrade materialisation (same), and recurring renewal
(``RenewSubscriptionUseCase``). They all build the *same* ``ChargeRequest``
(payer = company, CARD method) and differ only in amount, metadata (which
routes the email template) and description. Centralising the request assembly
here keeps those three paths from drifting on the charge wiring.
"""
from platform.features.billing.commerce.payments.domain.enums import MethodType
from platform.features.billing.commerce.payments.domain.schemas import ChargeRequest, PayerRef


def charge_plan(
    charge_use_case,
    company_id,
    *,
    amount,
    payment_method_id,
    metadata,
    description,
    currency: str = '',
):
    """Build and execute a plan charge. Returns the charge result (the caller
    inspects ``.status``); raising is left to the gateway/use case.

    ``currency`` empty ⇒ payment policy resolves company-country default.
    """
    return charge_use_case.execute(
        ChargeRequest(
            payer=PayerRef(company_id=company_id),
            amount=amount,
            currency=(currency or '').strip().upper(),
            method_type=MethodType.CARD,
            description=description,
            metadata=metadata,
        ),
        company_id=company_id,
        payment_method_id=payment_method_id,
    )
