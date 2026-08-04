from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import (
    IntakeView,
    InventoryBatchViewSet,
    PharmacyProductViewSet,
    StockMovementViewSet,
)

router = DefaultRouter()
router.register("pharmacy-products", PharmacyProductViewSet, basename="pharmacy-product")
router.register("batches", InventoryBatchViewSet, basename="batch")
router.register("movements", StockMovementViewSet, basename="movement")

urlpatterns = [
    path("intake", IntakeView.as_view(), name="intake"),
    *router.urls,
]
