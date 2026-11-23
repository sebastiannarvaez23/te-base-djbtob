"""Unit tests for OR and predictive ports (Fake adapters)."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from core.ai import (
    get_anomaly_detector,
    get_batch_grouper,
    get_demand_forecaster,
    get_document_extractor,
    get_picking_router,
)
from core.ai.domain.optimization.schemas import (
    BatchGroupRequest,
    BatchOrderRef,
    PickingRouteRequest,
    RouteStop,
)
from core.ai.domain.predictive.schemas import (
    AnomalyDetectionRequest,
    DemandForecastPoint,
    DemandForecastRequest,
)
from core.ai.infrastructure.optimization import FakeBatchGrouper, FakePickingRouter
from core.ai.infrastructure.predictive import FakeAnomalyDetector, FakeDemandForecaster
from core.ai.resilience import predict_or, solve_or
from core.errors import AppErrorCode
from core.errors.codes import ERROR_REGISTRY


@pytest.mark.unit
class TestOptimizationPorts:

    def test_factory_returns_fake_router(self):
        assert isinstance(get_picking_router(), FakePickingRouter)

    def test_fake_router_sequences_by_route_order(self):
        router = FakePickingRouter()
        result = router.route(
            PickingRouteRequest(
                warehouse_id='wh-1',
                required_quantity=Decimal('5'),
                candidates=[
                    RouteStop(position_id='p2', location_id='L2', sequence=2, quantity=Decimal('10')),
                    RouteStop(position_id='p1', location_id='L1', sequence=1, quantity=Decimal('3')),
                ],
            )
        )
        assert result.provider == 'fake'
        assert result.total_quantity == Decimal('5')
        assert result.allocations[0].position_id == 'p1'
        assert result.allocations[0].quantity == Decimal('3')
        assert result.allocations[1].position_id == 'p2'
        assert result.allocations[1].quantity == Decimal('2')

    def test_batch_grouper_chunks(self):
        grouper = get_batch_grouper()
        assert isinstance(grouper, FakeBatchGrouper)
        result = grouper.group(
            BatchGroupRequest(
                warehouse_id='wh-1',
                max_batch_size=2,
                orders=[
                    BatchOrderRef(order_id='o1'),
                    BatchOrderRef(order_id='o2'),
                    BatchOrderRef(order_id='o3'),
                ],
            )
        )
        assert len(result.batches) == 2
        assert result.batches[0].order_ids == ['o1', 'o2']
        assert result.batches[1].order_ids == ['o3']

    def test_solve_or_degrades(self):
        class Boom:
            provider_name = 'boom'

            def route(self, request):
                raise RuntimeError('solver down')

        result = solve_or(Boom(), PickingRouteRequest(warehouse_id='w', required_quantity=Decimal('1')))
        assert result.degraded
        assert result.allocations == []


@pytest.mark.unit
class TestPredictivePorts:

    def test_factory_returns_fake_forecaster(self):
        assert isinstance(get_demand_forecaster(), FakeDemandForecaster)

    def test_fake_forecast_repeats_last_history(self):
        forecaster = FakeDemandForecaster()
        result = forecaster.forecast(
            DemandForecastRequest(
                sku_id='SKU-1',
                horizon_days=3,
                history=[
                    DemandForecastPoint(period_start=date(2026, 1, 1), quantity=Decimal('10')),
                ],
            )
        )
        assert len(result.points) == 3
        assert all(p.quantity == Decimal('10') for p in result.points)

    def test_anomaly_detector_empty_by_default(self):
        detector = get_anomaly_detector()
        assert isinstance(detector, FakeAnomalyDetector)
        result = detector.detect(AnomalyDetectionRequest(entity_ids=['a']))
        assert result.signals == []

    def test_anomaly_forced_via_feature(self):
        detector = FakeAnomalyDetector()
        result = detector.detect(
            AnomalyDetectionRequest(
                entity_ids=['bal-1'],
                features={'force_anomaly': True},
            )
        )
        assert len(result.signals) == 1
        assert result.signals[0].entity_id == 'bal-1'

    def test_predict_or_degrades(self):
        class Boom:
            provider_name = 'boom'
            model_version = 'x'

            def forecast(self, request):
                raise RuntimeError('ml down')

        result = predict_or(
            Boom(),
            DemandForecastRequest(sku_id='SKU-1', horizon_days=1),
            feature='test',
        )
        assert result.degraded
        assert result.points == []


@pytest.mark.unit
class TestDocumentExtractorFactory:

    def test_fake_document_extractor(self):
        extractor = get_document_extractor()
        result = extractor.extract(b'%PDF', 'application/pdf', {'invoice_number': 'str'})
        assert result.provider == 'fake'
        assert result.degraded
        assert result.data['bytes'] == 4


@pytest.mark.unit
class TestAiBusyCode:

    def test_ai_busy_registered(self):
        entry = ERROR_REGISTRY[AppErrorCode.AI_BUSY]
        assert entry['http_status'] == 409

    def test_busy_payload_matches_registry(self):
        from client.features.communication.assistant.chat.realtime.consumer import (
            assistant_busy_error_payload,
        )
        payload = assistant_busy_error_payload()
        assert payload['code'] == AppErrorCode.AI_BUSY.value
        assert payload['detail'] == ERROR_REGISTRY[AppErrorCode.AI_BUSY]['detail']


@pytest.mark.unit
class TestOrMlKillSwitches:

    @override_settings(OR_ENABLED=False, OR_PROVIDER='custom')
    def test_or_disabled_raises_dedicated_code(self):
        from core.errors import ServerException
        with pytest.raises(ServerException) as exc:
            get_picking_router('custom')
        assert exc.value.code == AppErrorCode.AI_OR_DISABLED

    @override_settings(ML_ENABLED=False, ML_PROVIDER='custom')
    def test_ml_disabled_raises_dedicated_code(self):
        from core.errors import ServerException
        with pytest.raises(ServerException) as exc:
            get_demand_forecaster('custom')
        assert exc.value.code == AppErrorCode.AI_ML_DISABLED

    @override_settings(OR_ENABLED=False, OR_PROVIDER='fake')
    def test_or_fake_still_available_when_disabled(self):
        assert isinstance(get_picking_router('fake'), FakePickingRouter)
