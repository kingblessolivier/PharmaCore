"""Permission matrix: roles are bundles of permissions; SYS_ADMIN edits the matrix."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, Permission, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def cashier(db: None) -> User:
    u = User.objects.create_user(username="till", password="x")
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


@pytest.mark.django_db
def test_catalogue_seeded() -> None:
    assert Permission.objects.filter(code="sale.void").exists()
    assert Permission.objects.count() >= 20


@pytest.mark.django_db
def test_role_bundles_seeded() -> None:
    cashier = Role.objects.get(code="CASHIER")
    codes = set(cashier.permissions.values_list("code", flat=True))
    assert "sale.create" in codes
    assert "sale.void" not in codes  # cashiers can't void


@pytest.mark.django_db
def test_has_permission_via_role(cashier: User) -> None:
    assert cashier.has_permission("sale.create") is True
    assert cashier.has_permission("sale.void") is False
    assert cashier.has_permission("user.manage") is False


@pytest.mark.django_db
def test_sys_admin_implicitly_holds_all(sys_admin: User) -> None:
    assert sys_admin.has_permission("sale.void") is True
    assert sys_admin.has_permission("company.manage") is True
    assert len(sys_admin.permission_codes()) == Permission.objects.count()


@pytest.mark.django_db
def test_me_exposes_permissions(cashier: User) -> None:
    client = APIClient()
    tokens = client.post("/api/auth/login", {"username": "till", "password": "x"}).json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    perms = client.get("/api/auth/me").json()["permissions"]
    assert "sale.create" in perms and "sale.void" not in perms


@pytest.mark.django_db
def test_permissions_endpoint_admin_only(sys_admin: User, cashier: User) -> None:
    assert _auth(sys_admin).get("/api/permissions/").status_code == 200
    assert _auth(cashier).get("/api/permissions/").status_code == 403


@pytest.mark.django_db
def test_sys_admin_edits_role_matrix(sys_admin: User) -> None:
    cashier_role = Role.objects.get(code="CASHIER")
    resp = _auth(sys_admin).patch(
        f"/api/roles/{cashier_role.pk}/",
        {"permissions": ["sale.create", "sale.void"]},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    codes = set(cashier_role.permissions.values_list("code", flat=True))
    assert codes == {"sale.create", "sale.void"}
    assert AuditLog.objects.filter(action="UPDATE", entity_type="role").exists()


@pytest.mark.django_db
def test_org_admin_cannot_edit_role_matrix(db: None) -> None:
    org = Organization.objects.create(name="P", type=Organization.OrgType.RETAIL)
    org_admin = User.objects.create_user(username="mgr", password="x", organization=org)
    org_admin.roles.add(Role.objects.get(code="ORG_ADMIN"))
    role = Role.objects.get(code="CASHIER")
    resp = _auth(org_admin).patch(
        f"/api/roles/{role.pk}/", {"permissions": ["sale.void"]}, format="json"
    )
    assert resp.status_code == 403
