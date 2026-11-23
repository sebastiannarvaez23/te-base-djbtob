"""Excepciones internas del módulo analytics (no envelope HTTP)."""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base del dominio analytics."""


class AnalyticsDisabledError(AnalyticsError):
    """``ANALYTICS_ENABLED=false``."""


class PipelineNotFoundError(AnalyticsError):
    """pipeline_key no registrado en el registry."""


class PipelineStepError(AnalyticsError):
    """Fallo en extract / stage / transform / load."""

    def __init__(self, step: str, message: str, *, cause: BaseException | None = None):
        self.step = step
        self.cause = cause
        super().__init__(f'[{step}] {message}')


class AnalyticsQueryError(AnalyticsError):
    """Query inválida (p. ej. sin company_id — validado en schema)."""
