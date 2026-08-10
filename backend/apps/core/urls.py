from __future__ import annotations

from django.urls import path

from apps.core.uploads import ImageUploadView
from apps.core.views import (
    HealthView,
    MoneyCentreView,
    PharmacyDayView,
    PharmacyPerformanceView,
    PharmacySetupView,
    RootView,
)

urlpatterns = [
    path("", RootView.as_view(), name="root"),
    path("health", HealthView.as_view(), name="health"),
    path("api/uploads/image", ImageUploadView.as_view(), name="image-upload"),
    path("api/pharmacy/day/", PharmacyDayView.as_view(), name="pharmacy-day"),
    path("api/pharmacy/money/", MoneyCentreView.as_view(), name="pharmacy-money"),
    path("api/pharmacy/setup/", PharmacySetupView.as_view(), name="pharmacy-setup"),
    path(
        "api/pharmacy/performance/",
        PharmacyPerformanceView.as_view(),
        name="pharmacy-performance",
    ),
]
