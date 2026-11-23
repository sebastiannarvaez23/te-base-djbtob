"""Composition root for refund use cases."""
from platform.features.billing.commerce.payments.application.use_cases import RefundChargeUseCase
from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
from platform.features.billing.commerce.payments.infrastructure.routing.router import DefaultPaymentRouter
from platform.features.billing.commerce.payments.integration.adapters.country_currency_policy import (
    DjangoCountryCurrencyPolicy,
)
from platform.features.billing.subscription.subscription.infrastructure.repositories import (
    DjangoSubscriptionRepository,
)

from ..application.approve import ApproveRefundUseCase
from ..application.create import CreateRefundRequestUseCase
from ..application.evaluate import EvaluateRefundUseCase
from ..application.get_current import GetCurrentRefundUseCase
from ..application.list_admin import GetAdminRefundUseCase, ListRefundsUseCase
from ..application.process import ProcessRefundPayoutUseCase
from ..application.reject import RejectRefundUseCase
from .lookups import DjangoPeriodSnapshotLookup, DjangoRefundableChargeLookup
from .notifications import DjangoCompanyRecipientLookup, InboxRefundNotifier
from .payout import ChargeGatewayRefundAdapter
from .repositories import DjangoRefundRequestRepository


def _tickets():
    return DjangoRefundRequestRepository()


def _periods():
    return DjangoPeriodSnapshotLookup()


def _charges():
    return DjangoRefundableChargeLookup()


def _catalog():
    return DjangoSubscriptionRepository()


def _notifier():
    return InboxRefundNotifier()


def _recipients():
    return DjangoCompanyRecipientLookup()


def build_evaluate() -> EvaluateRefundUseCase:
    return EvaluateRefundUseCase(_tickets(), _periods(), _charges(), _catalog())


def build_get_current() -> GetCurrentRefundUseCase:
    return GetCurrentRefundUseCase(_tickets())


def _enqueue(ticket_id):
    from ..tasks.payout import process_refund_payout
    process_refund_payout.delay(str(ticket_id))


def _kill_company_sessions(company_id):
    from platform.features.security.identity.sessions.application.use_cases import (
        KillSessionsByCompanyUseCase,
    )
    from platform.features.security.identity.sessions.infrastructure.repositories import (
        DjangoSessionRepository,
    )
    return KillSessionsByCompanyUseCase(DjangoSessionRepository()).execute(company_id)


def build_create() -> CreateRefundRequestUseCase:
    return CreateRefundRequestUseCase(
        evaluate=build_evaluate(),
        tickets=_tickets(),
        periods=_periods(),
        charges=_charges(),
        notifier=_notifier(),
        recipients=_recipients(),
    )


def build_approve() -> ApproveRefundUseCase:
    return ApproveRefundUseCase(
        tickets=_tickets(),
        periods=_periods(),
        charges=_charges(),
        company_periods=_catalog(),
        notifier=_notifier(),
        recipients=_recipients(),
        enqueue=_enqueue,
        kill_company_sessions=_kill_company_sessions,
    )


def build_reject() -> RejectRefundUseCase:
    return RejectRefundUseCase(_tickets(), _notifier(), _recipients())


def build_list() -> ListRefundsUseCase:
    return ListRefundsUseCase(_tickets())


def build_get_admin() -> GetAdminRefundUseCase:
    return GetAdminRefundUseCase(_tickets())


def build_process() -> ProcessRefundPayoutUseCase:
    payout = ChargeGatewayRefundAdapter(
        RefundChargeUseCase(
            DjangoChargeRepository(),
            DefaultPaymentRouter(),
            currency_policy=DjangoCountryCurrencyPolicy(),
        ),
    )
    return ProcessRefundPayoutUseCase(
        tickets=_tickets(),
        charges=_charges(),
        payout=payout,
        notifier=_notifier(),
        recipients=_recipients(),
    )
