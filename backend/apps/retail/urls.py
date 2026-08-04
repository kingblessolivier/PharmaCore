from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.retail.views import DispensingViewSet, SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("dispensing", DispensingViewSet, basename="dispensing")

urlpatterns = [*router.urls]
