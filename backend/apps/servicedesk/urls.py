from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.servicedesk.views import TicketViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls
