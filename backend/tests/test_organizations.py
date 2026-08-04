"""Organizations & departments: tenant scoping, permissions, and audit."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Department, Organization, Role, User
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Depot", type=Organization.OrgType.DEPOT)


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def branch_user(retail: Organization) -> User:
    return User.objects.create_user(username="cashier", password="x", organization=retail)


@pytest.mark.django_db
def test_sys_admin_sees_all_orgs(
    sys_admin: User, depot: Organization, retail: Organization
) -> None:
    resp = _auth(sys_admin).get("/api/organizations/")
    assert resp.status_code == 200
    names = {o["name"] for o in resp.json()["results"]}
    assert {"Kigali Depot", "Kigali Central"} <= names


@pytest.mark.django_db
def test_branch_user_sees_only_own_org(branch_user: User, depot: Organization) -> None:
    resp = _auth(branch_user).get("/api/organizations/")
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()["results"]]
    assert names == ["Kigali Central"]  # not the depot


@pytest.mark.django_db
def test_non_admin_cannot_create_org(branch_user: User) -> None:
    resp = _auth(branch_user).post(
        "/api/organizations/", {"name": "Rogue", "type": "RETAIL"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_sys_admin_creates_org_and_audits(sys_admin: User) -> None:
    resp = _auth(sys_admin).post(
        "/api/organizations/", {"name": "New Depot", "type": "DEPOT"}, format="json"
    )
    assert resp.status_code == 201
    assert Organization.objects.filter(name="New Depot").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="organization").exists()


@pytest.mark.django_db
def test_department_unique_per_org(sys_admin: User, retail: Organization) -> None:
    Department.objects.create(organization=retail, code="CASHIER", name="Cashier")
    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(organization=retail, code="CASHIER", name="Cashier 2")


@pytest.mark.django_db
def test_admin_can_update_org(sys_admin: User, retail: Organization) -> None:
    resp = _auth(sys_admin).patch(
        f"/api/organizations/{retail.pk}/", {"tin": "999888777"}, format="json"
    )
    assert resp.status_code == 200
    retail.refresh_from_db()
    assert retail.tin == "999888777"
    assert AuditLog.objects.filter(action="UPDATE", entity_type="organization").exists()


@pytest.mark.django_db
def test_admin_can_delete_org(sys_admin: User, retail: Organization) -> None:
    resp = _auth(sys_admin).delete(f"/api/organizations/{retail.pk}/")
    assert resp.status_code == 204
    assert not Organization.objects.filter(pk=retail.pk).exists()
    assert AuditLog.objects.filter(action="DELETE", entity_type="organization").exists()


@pytest.mark.django_db
def test_non_admin_cannot_delete_org(branch_user: User, retail: Organization) -> None:
    resp = _auth(branch_user).delete(f"/api/organizations/{retail.pk}/")
    assert resp.status_code == 403
    assert Organization.objects.filter(pk=retail.pk).exists()
