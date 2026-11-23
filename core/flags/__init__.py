"""Release flags — portable evaluator from necore; django store stays in platform."""
from __future__ import annotations

from necore.flags import (  # noqa: F401
    FakeFlagStore,
    FlagDefinition,
    FlagEvaluator,
    FlagKeys,
    FlagScope,
    FlagStatus,
    FlagType,
    IFlagStore,
    IScopeMatcher,
    ScopeMatcherRegistry,
    ScopeType,
    build_default_registry,
    is_enabled,
)
from necore.flags import set_flag_store_factory

from .config import get_flag_store  # product factory (django | fake)
from .domain.schemas import FlagContext

# Ensure necore.is_enabled default path uses base factory when hosts call necore directly.
set_flag_store_factory(get_flag_store)

__all__ = [
    'is_enabled',
    'get_flag_store',
    'FlagKeys',
    'FlagContext',
    'FlagDefinition',
    'FlagScope',
    'FlagStatus',
    'FlagType',
    'ScopeType',
    'IFlagStore',
    'IScopeMatcher',
    'FlagEvaluator',
    'FakeFlagStore',
    'ScopeMatcherRegistry',
    'build_default_registry',
    'set_flag_store_factory',
]
