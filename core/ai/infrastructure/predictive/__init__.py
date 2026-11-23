"""Predictive adapter package."""

from .fake_provider import FakeAnomalyDetector, FakeDemandForecaster

__all__ = ['FakeDemandForecaster', 'FakeAnomalyDetector']
