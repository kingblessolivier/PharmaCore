"""Tenant-scoping helpers (deny-by-default multi-tenant access)."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.iam.models import Organization, User


def organizations_visible_to(user: User) -> QuerySet[Organization]:
    """Organizations a user may see.

    - SYS_ADMIN / superuser: all.
    - A user at a company's **HQ** branch: every branch in that company (HQ sees
      across the chain).
    - Everyone else: only their own organization.

    Deny by default: a user with no organization sees nothing.
    """
    all_orgs = Organization.objects.all()
    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return all_orgs
    org = user.organization
    if org is None:
        return Organization.objects.none()
    # HQ of a company sees all its branches; a branch sees only itself.
    if org.company_id and org.type == Organization.OrgType.HQ:
        return all_orgs.filter(company_id=org.company_id)
    return all_orgs.filter(pk=org.pk)
