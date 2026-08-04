from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.retail.views import SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")

urlpatterns = [*router.urls]
