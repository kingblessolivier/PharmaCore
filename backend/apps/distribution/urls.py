from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.distribution.views import StockOrderViewSet

router = DefaultRouter()
router.register("orders", StockOrderViewSet, basename="order")

urlpatterns = router.urls
