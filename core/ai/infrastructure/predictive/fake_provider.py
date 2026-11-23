"""Fake predictive adapters — no trained model; safe for CI and cold-start."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from time import perf_counter

from ...domain.predictive.interfaces import IAnomalyDetector, IDemandForecaster
from ...domain.predictive.schemas import (
    AnomalyDetectionRequest,
    AnomalyDetectionResult,
    AnomalySignal,
    DemandForecastPoint,
    DemandForecastRequest,
    DemandForecastResult,
)


class FakeDemandForecaster(IDemandForecaster):
    """Repeats last known demand (or zero) across the horizon."""

    provider_name = 'fake'
    model_version = 'fake-v0'

    def forecast(self, request: DemandForecastRequest) -> DemandForecastResult:
        start = perf_counter()
        last = (
            request.history[-1].quantity
            if request.history
            else Decimal('0')
        )
        base = request.history[-1].period_start if request.history else None
        points: list[DemandForecastPoint] = []
        horizon = max(1, int(request.horizon_days or 1))
        for day in range(horizon):
            period = (base + timedelta(days=day + 1)) if base else None
            if period is None:
                from datetime import date
                period = date.today() + timedelta(days=day + 1)
            points.append(DemandForecastPoint(period_start=period, quantity=last))
        return DemandForecastResult(
            sku_id=request.sku_id,
            points=points,
            model_version=self.model_version,
            provider=self.provider_name,
            latency_ms=int((perf_counter() - start) * 1000),
        )


class FakeAnomalyDetector(IAnomalyDetector):
    """Returns no signals unless ``features['force_anomaly']`` is truthy."""

    provider_name = 'fake'
    model_version = 'fake-v0'

    def detect(self, request: AnomalyDetectionRequest) -> AnomalyDetectionResult:
        start = perf_counter()
        signals: list[AnomalySignal] = []
        if request.features.get('force_anomaly'):
            for entity_id in request.entity_ids or ['unknown']:
                signals.append(
                    AnomalySignal(
                        entity_type=request.scope,
                        entity_id=entity_id,
                        score=1.0,
                        reason='forced_by_feature_flag',
                    )
                )
        return AnomalyDetectionResult(
            signals=signals,
            model_version=self.model_version,
            provider=self.provider_name,
            latency_ms=int((perf_counter() - start) * 1000),
        )
