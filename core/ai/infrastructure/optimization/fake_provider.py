"""Fake OR adapters — deterministic, no OR-Tools dependency."""

from __future__ import annotations

from time import perf_counter

from core.ids import uuid7

from ...domain.optimization.interfaces import IBatchGrouper, IPickingRouter
from ...domain.optimization.schemas import (
    BatchGroup,
    BatchGroupRequest,
    BatchGroupResult,
    PickingRouteRequest,
    PickingRouteResult,
    RouteStop,
)


class FakePickingRouter(IPickingRouter):
    """Orders candidates by ``sequence``, then location/position id."""

    provider_name = 'fake'

    def route(self, request: PickingRouteRequest) -> PickingRouteResult:
        start = perf_counter()
        required = request.required_quantity
        if required <= 0:
            return PickingRouteResult(
                provider=self.provider_name,
                latency_ms=int((perf_counter() - start) * 1000),
                degraded=True,
            )
        remaining = required
        allocations: list[RouteStop] = []
        ordered = sorted(
            request.candidates,
            key=lambda row: (row.sequence, row.location_id, row.position_id),
        )
        for idx, stop in enumerate(ordered):
            if stop.quantity <= 0:
                continue
            qty = min(stop.quantity, remaining)
            allocations.append(
                RouteStop(
                    position_id=stop.position_id,
                    location_id=stop.location_id,
                    sequence=idx,
                    quantity=qty,
                )
            )
            remaining -= qty
            if remaining == 0:
                break
        return PickingRouteResult(
            allocations=allocations,
            total_quantity=required - remaining,
            provider=self.provider_name,
            latency_ms=int((perf_counter() - start) * 1000),
            degraded=remaining > 0,
        )


class FakeBatchGrouper(IBatchGrouper):
    """Chunks orders into batches of ``max_batch_size`` (stable order)."""

    provider_name = 'fake'

    def group(self, request: BatchGroupRequest) -> BatchGroupResult:
        start = perf_counter()
        size = max(1, int(request.max_batch_size or 1))
        batches: list[BatchGroup] = []
        ids = [o.order_id for o in request.orders]
        for i in range(0, len(ids), size):
            chunk = ids[i : i + size]
            batches.append(BatchGroup(batch_id=str(uuid7()), order_ids=chunk))
        return BatchGroupResult(
            batches=batches,
            provider=self.provider_name,
            latency_ms=int((perf_counter() - start) * 1000),
        )
