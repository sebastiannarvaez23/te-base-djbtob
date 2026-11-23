"""Registro pipeline_key → IPipeline."""

from __future__ import annotations

from core.analytics.domain.exceptions import PipelineNotFoundError
from core.analytics.domain.interfaces import IPipeline

_REGISTRY: dict[str, type[IPipeline]] = {}


def register_pipeline(key: str, cls: type[IPipeline]) -> None:
    _REGISTRY[key] = cls


def get_pipeline_class(key: str) -> type[IPipeline] | None:
    return _REGISTRY.get(key)


def registered_pipeline_keys() -> list[str]:
    return sorted(_REGISTRY.keys())


def clear_registry() -> None:
    """Solo tests."""
    _REGISTRY.clear()


class PipelineRegistry:
    def resolve(self, key: str) -> type[IPipeline]:
        cls = get_pipeline_class(key)
        if cls is None:
            raise PipelineNotFoundError(f'Unknown pipeline_key={key!r}')
        return cls

    def register(self, key: str, cls: type[IPipeline]) -> None:
        register_pipeline(key, cls)

    def create(self, key: str) -> IPipeline:
        return self.resolve(key)()
