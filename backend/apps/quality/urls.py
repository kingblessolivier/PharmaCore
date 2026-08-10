from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.quality.views import CapaActionViewSet, QualityCaseViewSet

router = DefaultRouter()
router.register("cases", QualityCaseViewSet, basename="quality-case")
router.register("actions", CapaActionViewSet, basename="capa-action")

urlpatterns = router.urls
