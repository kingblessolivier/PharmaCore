from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.inventory.views import PharmacyProductViewSet

router = DefaultRouter()
router.register("pharmacy-products", PharmacyProductViewSet, basename="pharmacy-product")

urlpatterns = router.urls
