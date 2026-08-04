from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.distribution.views import GRNViewSet, InTransitStockViewSet, StockOrderViewSet

router = DefaultRouter()
router.register("orders", StockOrderViewSet, basename="order")
router.register("grns", GRNViewSet, basename="grn")
router.register("in-transit", InTransitStockViewSet, basename="in-transit")

urlpatterns = router.urls
