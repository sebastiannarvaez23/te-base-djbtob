"""OR / optimization ports (cubo 4). Solvers live behind these contracts."""

from abc import ABC, abstractmethod

from .schemas import (
    BatchGroupRequest,
    BatchGroupResult,
    PickingRouteRequest,
    PickingRouteResult,
)


class IPickingRouter(ABC):
    """Sequence pick stops to minimize travel (state-only; no historical ML)."""

    @abstractmethod
    def route(self, request: PickingRouteRequest) -> PickingRouteResult:
        ...


class IBatchGrouper(ABC):
    """Group orders into waves/batches to reduce trips."""

    @abstractmethod
    def group(self, request: BatchGroupRequest) -> BatchGroupResult:
        ...
