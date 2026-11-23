"""
ViewSet REST del módulo de pagos.

Valida entrada con RequestBody, arma schemas Pydantic, instancia
repositorio + router, y delega al use case.
"""

from decimal import Decimal
from typing import Optional

from rest_framework import viewsets

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

from ..application.use_cases import (
    CancelChargeUseCase,
    CaptureChargeUseCase,
    ConfirmChargeUseCase,
    CreateChargeUseCase,
    FetchChargeUseCase,
    GetChargeByIdUseCase,
    GetChargesByCompanyUseCase,
    RefundChargeUseCase,
)
from ..domain.enums import MethodType
from ..domain.schemas import CardData, ChargeRequest, PayerRef
from ..infrastructure.repositories import DjangoChargeRepository
from ..infrastructure.routing.router import DefaultPaymentRouter
from ..integration.adapters.country_currency_policy import DjangoCountryCurrencyPolicy
from .bodies import (
    CancelChargeBody,
    CaptureChargeBody,
    ConfirmChargeBody,
    CreateChargeBody,
    RefundChargeBody,
)
from .queries import ChargeListQuery


class ChargeViewSet(viewsets.ViewSet):
    """Explicit charge lifecycle actions only (no ModelViewSet defaults)."""

    def _repo(self) -> DjangoChargeRepository:
        return DjangoChargeRepository()

    def _router(self) -> DefaultPaymentRouter:
        return DefaultPaymentRouter()

    def _currency_policy(self) -> DjangoCountryCurrencyPolicy:
        return DjangoCountryCurrencyPolicy()

    @validated_query(ChargeListQuery)
    def _list_charges(self, request, company_id, *, query: PaginatedQuery):
        result = GetChargesByCompanyUseCase(self._repo()).execute(company_id, query)
        return wrap_response({
            'items': [c.model_dump(mode='json') for c in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    def list(self, request, *args, **kwargs):
        return self._list_charges(request, request.tenant.id)

    def list_by_company(self, request, *args, **kwargs):
        return self._list_charges(request, kwargs.get('company_id'))

    def retrieve(self, request, *args, **kwargs):
        result = GetChargeByIdUseCase(self._repo()).execute(kwargs.get('pk'))
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CreateChargeBody)
    def create(self, request, *args, body: dict, **kwargs):
        validated = body

        method_type = MethodType(validated['method_type'])

        card_number = validated.get('card_number', '') or ''
        card: Optional[CardData] = None
        if card_number and method_type == MethodType.CARD:
            card = CardData(
                number=card_number,
                exp_month=validated.get('card_exp_month'),
                exp_year=validated.get('card_exp_year'),
                cvc=validated.get('card_cvc', '') or '',
                holder_name=validated.get('card_holder', '') or '',
            )

        raw_currency = (validated.get('currency') or '').strip().upper()
        charge_request = ChargeRequest(
            payer=PayerRef(company_id=request.tenant.id),
            amount=Decimal(str(validated['amount'])),
            currency=raw_currency,
            method_type=method_type,
            description=validated.get('description', '') or '',
            gateway_payment_method_id=validated.get('gateway_payment_method_id', '') or '',
            card=card,
            return_url=validated.get('return_url', '') or '',
            cancel_url=validated.get('cancel_url', '') or '',
            metadata=validated.get('metadata') or {},
        )

        result = CreateChargeUseCase(
            self._repo(), self._router(), currency_policy=self._currency_policy(),
        ).execute(
            charge_request,
            company_id=request.tenant.id,
            idempotency_key=validated.get('idempotency_key') or None,
            invoice_id=validated.get('invoice_id'),
            payment_method_id=validated.get('payment_method_id'),
        )
        audit_log(request, 'Charge', result.id, 'CREATE',
                  f"Charge created: {result.gateway_provider}/{result.gateway_charge_id} status={result.status.value}")
        return wrap_response(result.model_dump(mode='json'), status_code=201,
                             message='The charge has been created successfully.')

    @validated_body(ConfirmChargeBody)
    def confirm(self, request, *args, body: dict, **kwargs):
        result = ConfirmChargeUseCase(self._repo(), self._router()).execute(
            kwargs.get('pk'),
            payload = body.get('payload') or None,
        )
        audit_log(request, 'Charge', result.id, 'CONFIRM',
                  f'Charge confirmed: status={result.status.value}')
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CaptureChargeBody)
    def capture(self, request, *args, body: dict, **kwargs):
        amount = body.get('amount')
        result = CaptureChargeUseCase(self._repo(), self._router()).execute(
            kwargs.get('pk'),
            amount=Decimal(str(amount)) if amount is not None else None,
        )
        audit_log(request, 'Charge', result.id, 'CAPTURE',
                  f'Charge captured: status={result.status.value}')
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CancelChargeBody)
    def cancel(self, request, *args, body: dict, **kwargs):
        reason = body.get('reason', '') or ''
        result = CancelChargeUseCase(self._repo(), self._router()).execute(
            kwargs.get('pk'),
            reason=reason,
        )
        audit_log(request, 'Charge', result.id, 'CANCEL',
                  f'Charge canceled: reason="{reason}"')
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(RefundChargeBody)
    def refund(self, request, *args, body: dict, **kwargs):
        validated = body
        amount = validated.get('amount')
        raw_currency = (validated.get('currency') or '').strip().upper() or None
        result = RefundChargeUseCase(
            self._repo(), self._router(), currency_policy=self._currency_policy(),
        ).execute(
            kwargs.get('pk'),
            amount=Decimal(str(amount)) if amount is not None else None,
            reason=validated.get('reason', '') or '',
            currency=raw_currency,
        )
        audit_log(request, 'Charge', result.id, 'REFUND',
                  f'Charge refunded: status={result.status.value}')
        return wrap_response(result.model_dump(mode='json'))

    def sync(self, request, *args, **kwargs):
        """Reconcilia el estado local consultando al provider."""
        result = FetchChargeUseCase(self._repo(), self._router()).execute(kwargs.get('pk'))
        return wrap_response(result.model_dump(mode='json'))
