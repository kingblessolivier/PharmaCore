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
from apps.distribution.views_marketplace import (
    AvailabilityView,
    BackorderViewSet,
    DemandBoardView,
    DistributionOverviewView,
    PublishListingView,
    RepPerformanceView,
    ReturnActionsView,
    SourceDemandView,
    StorefrontView,
    TradingPartnersView,
    VanActionsView,
    VanManifestView,
    VanMovementViewSet,
    VanStockViewSet,
    VerifyListingImageView,
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
router.register("backorders", BackorderViewSet, basename="backorder")
router.register("van-stock", VanStockViewSet, basename="van-stock")
router.register("van-movements", VanMovementViewSet, basename="van-movement")

urlpatterns = [
    path("aging/", AgingView.as_view(), name="aging"),
    path("overview/", DistributionOverviewView.as_view(), name="distribution-overview"),
    # Storefront
    path("storefront/", StorefrontView.as_view(), name="storefront"),
    path("trading-partners/", TradingPartnersView.as_view(), name="trading-partners"),
    path("storefront/availability/", AvailabilityView.as_view(), name="availability"),
    path("storefront/publish/", PublishListingView.as_view(), name="publish-listing"),
    path(
        "listings/<int:pk>/verify-image/",
        VerifyListingImageView.as_view(),
        name="verify-listing-image",
    ),
    # Demand-driven sourcing
    path("demand/", DemandBoardView.as_view(), name="demand-board"),
    path("demand/source/", SourceDemandView.as_view(), name="source-demand"),
    # Returns
    path("returns/<int:pk>/<str:verb>/", ReturnActionsView.as_view(), name="return-actions"),
    # Van sales
    path("sales-reps/<int:pk>/van/", VanManifestView.as_view(), name="van-manifest"),
    path("sales-reps/<int:pk>/van/<str:verb>/", VanActionsView.as_view(), name="van-actions"),
    path("rep-performance/", RepPerformanceView.as_view(), name="rep-performance"),
    *router.urls,
]
