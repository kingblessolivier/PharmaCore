from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import (
    BatchRecallViewSet,
    BinLocationViewSet,
    IntakeView,
    InventoryBatchViewSet,
    PharmacyProductViewSet,
    QualityCheckViewSet,
    StockCountViewSet,
    StockDisposalViewSet,
    StockMovementViewSet,
    StorageZoneViewSet,
    TemperatureLogViewSet,
    TemperatureSensorViewSet,
)

router = DefaultRouter()
router.register("pharmacy-products", PharmacyProductViewSet, basename="pharmacy-product")
router.register("batches", InventoryBatchViewSet, basename="batch")
router.register("movements", StockMovementViewSet, basename="movement")
router.register("storage-zones", StorageZoneViewSet, basename="storage-zone")
router.register("bin-locations", BinLocationViewSet, basename="bin-location")
router.register("temp-sensors", TemperatureSensorViewSet, basename="temp-sensor")
router.register("temp-logs", TemperatureLogViewSet, basename="temp-log")
router.register("quality-checks", QualityCheckViewSet, basename="quality-check")
router.register("recalls", BatchRecallViewSet, basename="recall")
router.register("stock-counts", StockCountViewSet, basename="stock-count")
router.register("disposals", StockDisposalViewSet, basename="disposal")

urlpatterns = [
    path("intake", IntakeView.as_view(), name="intake"),
    *router.urls,
]
