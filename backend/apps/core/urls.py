from __future__ import annotations

from django.urls import path

from apps.core.views import HealthView, RootView

urlpatterns = [
    path("", RootView.as_view(), name="root"),
    path("health", HealthView.as_view(), name="health"),
]
