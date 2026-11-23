"""Predictive ML ports (cubo 3). Training/serving adapters implement these."""

from abc import ABC, abstractmethod

from .schemas import (
    AnomalyDetectionRequest,
    AnomalyDetectionResult,
    DemandForecastRequest,
    DemandForecastResult,
)


class IDemandForecaster(ABC):
    """Forecast demand for a SKU / warehouse horizon."""

    @abstractmethod
    def forecast(self, request: DemandForecastRequest) -> DemandForecastResult:
        ...


class IAnomalyDetector(ABC):
    """Detect anomalous inventory or transaction patterns."""

    @abstractmethod
    def detect(self, request: AnomalyDetectionRequest) -> AnomalyDetectionResult:
        ...
