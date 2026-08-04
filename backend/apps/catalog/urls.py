from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.catalog.views import ManufacturerViewSet, ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")

urlpatterns = router.urls
