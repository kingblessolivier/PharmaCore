"""Admin Users API: org-scoped, role assignment, audited."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central", type=Organization.OrgType.RETAIL)


@pytest.fixture
def other(db: None) -> Organization:
    return Organization.objects.create(name="Other Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def org_admin(retail: Organization) -> User:
    u = User.objects.create_user(username="mgr", password="x", organization=retail)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


@pytest.mark.django_db
def test_admin_creates_user_with_roles(sys_admin: User, retail: Organization) -> None:
    resp = _auth(sys_admin).post(
        "/api/users/",
        {
            "username": "cashier1",
            "password": "s3cret-pass",
            "organization": retail.pk,
            "roles": ["CASHIER"],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    u = User.objects.get(username="cashier1")
    assert u.check_password("s3cret-pass")
    assert u.has_role("CASHIER")
    assert u.organization_id == retail.pk
    assert AuditLog.objects.filter(action="CREATE", entity_type="user").exists()


@pytest.mark.django_db
def test_non_admin_cannot_list_users(retail: Organization) -> None:
    plain = User.objects.create_user(username="plain", password="x", organization=retail)
    assert _auth(plain).get("/api/users/").status_code == 403


@pytest.mark.django_db
def test_org_admin_scoped_to_own_org(
    org_admin: User, retail: Organization, other: Organization
) -> None:
    User.objects.create_user(username="mine", password="x", organization=retail)
    User.objects.create_user(username="theirs", password="x", organization=other)
    resp = _auth(org_admin).get("/api/users/")
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.json()["results"]}
    assert "mine" in usernames and "theirs" not in usernames


@pytest.mark.django_db
def test_org_admin_cannot_create_in_other_org(org_admin: User, other: Organization) -> None:
    resp = _auth(org_admin).post(
        "/api/users/",
        {"username": "x2", "password": "s3cret-pass", "organization": other.pk},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_updates_roles_and_deactivates(sys_admin: User, retail: Organization) -> None:
    u = User.objects.create_user(username="u1", password="x", organization=retail)
    resp = _auth(sys_admin).patch(
        f"/api/users/{u.pk}/", {"roles": ["PHARMACIST"], "is_active": False}, format="json"
    )
    assert resp.status_code == 200
    u.refresh_from_db()
    assert u.has_role("PHARMACIST") and u.is_active is False


@pytest.mark.django_db
def test_roles_endpoint_lists_seeded_roles(sys_admin: User) -> None:
    resp = _auth(sys_admin).get("/api/roles/")
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()}
    assert "CASHIER" in codes and "SYS_ADMIN" in codes
