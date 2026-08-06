from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.approvals.views import ApprovalRequestViewSet

router = DefaultRouter()
router.register("requests", ApprovalRequestViewSet, basename="approval-request")

urlpatterns = router.urls
