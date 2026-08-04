"""Helpers to raise operational notifications (order lifecycle, payments, alerts)."""

from __future__ import annotations

from apps.iam.models import Organization, User
from apps.workspace.models import Notification


def notify_org_admins(
    *,
    organization: Organization,
    title: str,
    body: str = "",
    link_entity_type: str = "",
    link_entity_id: str = "",
    exclude_user_id: int | None = None,
    dedupe: bool = False,
) -> int:
    """Create a SYSTEM notification for every active org-admin of ``organization``.

    Returns how many were created. With ``dedupe`` set, skips a recipient who
    already has an unread notification with the same title + link (so a daily
    alert command doesn't pile up duplicates)."""
    recipients = User.objects.filter(
        organization=organization, is_active=True, roles__code="ORG_ADMIN"
    ).distinct()
    made = 0
    for user in recipients:
        if exclude_user_id and user.pk == exclude_user_id:
            continue
        if (
            dedupe
            and Notification.objects.filter(
                recipient=user,
                is_read=False,
                title=title,
                link_entity_type=link_entity_type,
                link_entity_id=link_entity_id,
            ).exists()
        ):
            continue
        Notification.objects.create(
            recipient=user,
            type=Notification.Type.SYSTEM,
            title=title,
            body=body,
            link_entity_type=link_entity_type,
            link_entity_id=link_entity_id,
        )
        made += 1
    return made
