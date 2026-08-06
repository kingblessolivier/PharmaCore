from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import (
    BatchRecallViewSet,
    BinLocationViewSet,
    ConsignmentAgreementViewSet,
    ConsignmentConsumptionViewSet,
    ConsignmentSettlementViewSet,
    EpcisEventViewSet,
    ExcursionInvestigationViewSet,
    IntakeView,
    InventoryBatchViewSet,
    PharmacyProductViewSet,
    PickTaskViewSet,
    PickWaveViewSet,
    PutawayRuleViewSet,
    QualityCheckViewSet,
    ReorderRuleViewSet,
    SensorCalibrationViewSet,
    SerialUnitViewSet,
    StockCountViewSet,
    StockDisposalViewSet,
    StockMovementViewSet,
    StorageZoneViewSet,
    TemperatureLogViewSet,
    TemperatureSensorViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("pharmacy-products", PharmacyProductViewSet, basename="pharmacy-product")
router.register("batches", InventoryBatchViewSet, basename="batch")
router.register("movements", StockMovementViewSet, basename="movement")
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("storage-zones", StorageZoneViewSet, basename="storage-zone")
router.register("bin-locations", BinLocationViewSet, basename="bin-location")
router.register("temp-sensors", TemperatureSensorViewSet, basename="temp-sensor")
router.register("temp-logs", TemperatureLogViewSet, basename="temp-log")
router.register("calibrations", SensorCalibrationViewSet, basename="calibration")
router.register("excursions", ExcursionInvestigationViewSet, basename="excursion")
router.register("quality-checks", QualityCheckViewSet, basename="quality-check")
router.register("recalls", BatchRecallViewSet, basename="recall")
router.register("stock-counts", StockCountViewSet, basename="stock-count")
router.register("disposals", StockDisposalViewSet, basename="disposal")
router.register("reorder-rules", ReorderRuleViewSet, basename="reorder-rule")
router.register("serial-units", SerialUnitViewSet, basename="serial-unit")
router.register("epcis-events", EpcisEventViewSet, basename="epcis-event")
router.register("consignments", ConsignmentAgreementViewSet, basename="consignment")
router.register(
    "consignment-consumptions", ConsignmentConsumptionViewSet, basename="consignment-consumption"
)
router.register(
    "consignment-settlements", ConsignmentSettlementViewSet, basename="consignment-settlement"
)
router.register("putaway-rules", PutawayRuleViewSet, basename="putaway-rule")
router.register("pick-waves", PickWaveViewSet, basename="pick-wave")
router.register("pick-tasks", PickTaskViewSet, basename="pick-task")

urlpatterns = [
    path("intake", IntakeView.as_view(), name="intake"),
    *router.urls,
]
