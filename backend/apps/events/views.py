"""Read-only API surface for the events app (F1 ships a health endpoint only).

The full outbox / event-stream view (sys-admin inbox) lands in a later PR —
see ``docs/development/finance-hr-roadmap.md`` F1.4. Keeping this minimal here
so F1 stays reviewable.
"""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def health(request):  # pragma: no cover - trivial
    """Trivial endpoint — proves the app is mounted. Returns 200."""
    return Response({"status": "ok", "app": "events"})