"""Health & readiness endpoints (Phase 0 walking skeleton)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe — confirms the API is up."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "PharmaCore API",
                "version": settings.VERSION,
                "environment": settings.MEDLINK_ENV,
            }
        )


class RootView(APIView):
    """Root banner."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = {
            "service": "PharmaCore API",
            "version": settings.VERSION,
            "docs": "/api/docs/",
        }
        return Response(data)
