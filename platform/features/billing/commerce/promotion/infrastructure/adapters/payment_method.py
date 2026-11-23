"""Creates a stored payment method from onboarding-collected card data."""

import uuid

from platform.features.billing.commerce.promotion.domain.interfaces import IPaymentMethodCreatorPort


def _detect_provider(last4: str) -> str:
    return 'visa'


class DjangoPaymentMethodCreator(IPaymentMethodCreatorPort):

    def create_from_onboarding(self, *, company_id: uuid.UUID, payment_data: dict) -> uuid.UUID:
        from platform.features.billing.commerce.payment_method.application.use_cases import (
            CreatePaymentMethodUseCase,
        )
        from platform.features.billing.commerce.payment_method.domain.schemas import CreatePaymentMethodSchema
        from platform.features.billing.commerce.payment_method.infrastructure.repositories import (
            DjangoPaymentMethodRepository,
        )

        expiry_month = payment_data.get('expiry_month', '')
        expiry_year = str(payment_data.get('expiry_year', ''))
        expiry = f'{expiry_month:02d}/{expiry_year[-2:]}' if isinstance(expiry_month, int) else ''
        pm = CreatePaymentMethodUseCase(DjangoPaymentMethodRepository()).execute(
            CreatePaymentMethodSchema(
                company_id=company_id,
                name='Tarjeta principal',
                provider=_detect_provider(payment_data.get('last4', '')),
                holder=payment_data.get('holder', ''),
                last4=payment_data.get('last4', ''),
                expiry=expiry,
                is_active=True,
            )
        )
        return pm.id
