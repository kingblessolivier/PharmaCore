from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.distribution.views import (
    AgingView,
    GRNViewSet,
    InTransitStockViewSet,
    StockOrderViewSet,
)

router = DefaultRouter()
router.register("orders", StockOrderViewSet, basename="order")
router.register("grns", GRNViewSet, basename="grn")
router.register("in-transit", InTransitStockViewSet, basename="in-transit")

urlpatterns = [
    path("aging/", AgingView.as_view(), name="aging"),
    *router.urls,
]
