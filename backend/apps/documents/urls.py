from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.documents.views import DocumentVerifyView, DocumentViewSet

router = DefaultRouter()
router.register("", DocumentViewSet, basename="document")

urlpatterns = [
    path("verify/<str:token>/", DocumentVerifyView.as_view(), name="document-verify"),
    *router.urls,
]
