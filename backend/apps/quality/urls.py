from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.quality.audit_api import AuditEngagementViewSet, AuditFindingViewSet
from apps.quality.views import CapaActionViewSet, QualityCaseViewSet

router = DefaultRouter()
router.register("cases", QualityCaseViewSet, basename="quality-case")
router.register("actions", CapaActionViewSet, basename="capa-action")
router.register("audits", AuditEngagementViewSet, basename="audit-engagement")
router.register("findings", AuditFindingViewSet, basename="audit-finding")

urlpatterns = router.urls
