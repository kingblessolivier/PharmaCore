"""Tenant-scoping helpers (deny-by-default multi-tenant access)."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.iam.models import Organization, User


def organizations_visible_to(user: User) -> QuerySet[Organization]:
    """Organizations a user may see.

    SYS_ADMIN / superuser see all; everyone else sees only their own organization.
    (Hierarchy/descendant visibility is a later refinement.) Deny by default: a user
    with no organization sees nothing.
    """
    all_orgs = Organization.objects.all()
    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return all_orgs
    if user.organization_id:
        return all_orgs.filter(pk=user.organization_id)
    return Organization.objects.none()
