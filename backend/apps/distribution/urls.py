from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.distribution.views import (
    AgingView,
    CustomerReturnViewSet,
    DepotProductListingViewSet,
    GRNViewSet,
    InTransitStockViewSet,
    JourneyPlanViewSet,
    SalesRepresentativeViewSet,
    SalesVisitLogViewSet,
    StockOrderViewSet,
    TenderContractViewSet,
)

router = DefaultRouter()
router.register("orders", StockOrderViewSet, basename="order")
router.register("grns", GRNViewSet, basename="grn")
router.register("in-transit", InTransitStockViewSet, basename="in-transit")
router.register("listings", DepotProductListingViewSet, basename="listing")
router.register("sales-reps", SalesRepresentativeViewSet, basename="sales-rep")
router.register("journey-plans", JourneyPlanViewSet, basename="journey-plan")
router.register("visit-logs", SalesVisitLogViewSet, basename="visit-log")
router.register("tenders", TenderContractViewSet, basename="tender")
router.register("returns", CustomerReturnViewSet, basename="customer-return")

urlpatterns = [
    path("aging/", AgingView.as_view(), name="aging"),
    *router.urls,
]
