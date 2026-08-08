"""Can the authority model actually be configured, and can it be escaped?

R1–R4 landed in #93 and were enforced everywhere they were checked. What nobody
checked was whether the two inputs they run on could be *set*:

* ``reports_to`` was accepted by the admin serializer and settable from no screen,
  so every escalation chain was empty;
* ``approval_limit`` was not on the serializer at all, so a per-person ceiling
  could not be granted by any means.

And R4 — you cannot give away what you do not hold — was called from exactly one
place, reassigning an approval. Assigning a **role** was unchecked, which makes
every other rule optional: anyone who can administer users could grant themselves
past it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.iam import authority
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def person(org, *codes, limit=None):
    user = User.objects.create_user(
        username=f"u{User.objects.count()}", password="pw", organization=org
    )
    for code in codes:
        user.roles.add(Role.objects.get(code=code))
    if limit is not None:
        user.approval_limit = limit
        user.save()
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# The inputs can be set at all
# ---------------------------------------------------------------------------


def test_an_admin_can_set_who_someone_reports_to(org):
    """Without this, escalation walks a chain that is always empty."""
    admin = person(org, "ORG_ADMIN")
    manager = person(org, "BRANCH_MANAGER")
    clerk = person(org, "CASHIER")

    resp = client_for(admin).patch(
        f"/api/users/{clerk.pk}/", {"reports_to": manager.pk}, format="json"
    )
    assert resp.status_code == 200, resp.content
    clerk.refresh_from_db()
    assert clerk.reports_to_id == manager.pk
    assert [u.pk for u in authority.escalation_chain(clerk)] == [manager.pk]


def test_an_admin_can_set_a_personal_approval_limit(org):
    """The field existed on the model and on no serializer."""
    admin = person(org, "ORG_ADMIN")
    deputy = person(org, "HR_MANAGER")

    resp = client_for(admin).patch(
        f"/api/users/{deputy.pk}/", {"approval_limit": "60000000"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    deputy.refresh_from_db()
    assert authority.approval_limit(deputy) == Decimal("60000000")


def test_the_limit_is_readable_back(org):
    admin = person(org, "ORG_ADMIN")
    target = person(org, "PHARMACIST", limit=Decimal("750000"))
    body = client_for(admin).get(f"/api/users/{target.pk}/").json()
    assert body["approval_limit"] == "750000.00"
    assert "reports_to" in body


# ---------------------------------------------------------------------------
# R4 — the ceiling on what an admin may hand out
# ---------------------------------------------------------------------------


def test_an_org_admin_cannot_grant_a_role_holding_permissions_they_lack(org):
    """Otherwise every other rule is optional: grant yourself past it."""
    admin = person(org, "ORG_ADMIN")
    target = person(org, "CASHIER")

    # SYS_ADMIN carries no explicit permission rows — it holds them implicitly —
    # so a set-comparison alone waved it through. This is the escalation an org
    # admin must not be able to perform.
    resp = client_for(admin).patch(
        f"/api/users/{target.pk}/", {"roles": ["SYS_ADMIN"]}, format="json"
    )
    assert resp.status_code == 403, resp.content
    target.refresh_from_db()
    assert not target.has_role("SYS_ADMIN")


def test_an_admin_may_grant_a_role_within_what_they_hold(org):
    admin = person(org, "ORG_ADMIN")
    target = person(org, "CASHIER")
    resp = client_for(admin).patch(
        f"/api/users/{target.pk}/", {"roles": ["PHARMACIST"]}, format="json"
    )
    assert resp.status_code == 200, resp.content
    target.refresh_from_db()
    assert target.has_role("PHARMACIST")


def test_an_admin_cannot_grant_a_limit_above_their_own(org):
    """A ceiling you can raise for yourself is not a ceiling."""
    admin = person(org, "ORG_ADMIN", limit=Decimal("2000000"))
    target = person(org, "PHARMACIST")

    resp = client_for(admin).patch(
        f"/api/users/{target.pk}/", {"approval_limit": "9000000"}, format="json"
    )
    assert resp.status_code == 403
    assert "your own is" in str(resp.content)

    ok = client_for(admin).patch(
        f"/api/users/{target.pk}/", {"approval_limit": "1500000"}, format="json"
    )
    assert ok.status_code == 200, ok.content


def test_a_superuser_is_not_capped(org):
    """The break-glass account has to be able to set the first ceiling."""
    root = User.objects.create_superuser(username="root", password="pw", email="r@x.rw")
    root.organization = org
    root.save()
    target = person(org, "CASHIER")

    resp = client_for(root).patch(
        f"/api/users/{target.pk}/",
        {"roles": ["SYS_ADMIN"], "approval_limit": "99000000"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def test_the_ceiling_applies_on_create_as_well_as_update(org):
    """Otherwise the rule is bypassed by making a new user instead of editing one."""
    admin = person(org, "ORG_ADMIN")
    resp = client_for(admin).post(
        "/api/users/",
        {
            "username": "smuggled",
            "password": "correct-horse-battery",
            "organization": org.pk,
            "roles": ["SYS_ADMIN"],
        },
        format="json",
    )
    assert resp.status_code == 403, resp.content
    assert not User.objects.filter(username="smuggled").exists()
