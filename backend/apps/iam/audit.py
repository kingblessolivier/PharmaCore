"""Helper for writing audit entries."""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request

from apps.iam.models import AuditLog, User


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit(
    *,
    action: str,
    user: User | None = None,
    entity_type: str = "",
    entity_id: str = "",
    changes: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Write an append-only audit entry."""
    return AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        ip_address=_client_ip(request),
    )
