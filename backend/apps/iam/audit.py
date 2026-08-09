"""Helper for writing audit entries."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework.request import Request

from apps.iam.models import AuditLog, Organization, User


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _json_safe(value: Any) -> Any:
    """Make an audit payload storable in a JSONField.

    Stock quantities became Decimals when the shelf learned about half tablets,
    and `json.dumps` refuses a Decimal. Coercing here rather than at each call
    site means no subsystem has to remember: an audit write must never be the
    thing that fails an otherwise valid operation.

    Decimals become strings rather than floats on purpose — a quantity that
    round-trips through a float is a quantity that can come back as 2.9999.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    return value


def record_audit(
    *,
    action: str,
    user: User | None = None,
    organization: Organization | None = None,
    entity_type: str = "",
    entity_id: str = "",
    changes: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Write an append-only audit entry.

    ``organization`` stamps which pharmacy the action belongs to (for org-scoped
    logs). If omitted, it falls back to the acting user's organization.
    """
    if organization is None and user is not None:
        organization = user.organization
    return AuditLog.objects.create(
        user=user,
        organization=organization,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=_json_safe(changes),
        ip_address=_client_ip(request),
    )
