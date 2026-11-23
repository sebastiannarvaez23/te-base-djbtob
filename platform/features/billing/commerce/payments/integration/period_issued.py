"""Subscribe payments to billing-period lifecycle events."""
from platform.features.billing.commerce.payments.application.bind_period import BindChargeToPeriodUseCase
from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
from platform.features.billing.subscription.subscription.domain.events import PeriodIssued


class PeriodIssuedChargeListener:
    def __init__(self, charge_repo_factory=DjangoChargeRepository):
        self._charge_repo_factory = charge_repo_factory

    def on_period_issued(self, event: PeriodIssued) -> None:
        if event.charge_id is None:
            return
        BindChargeToPeriodUseCase(self._charge_repo_factory()).execute(
            event.charge_id, event.period_id,
        )
