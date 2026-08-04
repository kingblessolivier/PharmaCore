from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.distribution.views import GRNViewSet, StockOrderViewSet

router = DefaultRouter()
router.register("orders", StockOrderViewSet, basename="order")
router.register("grns", GRNViewSet, basename="grn")

urlpatterns = router.urls
