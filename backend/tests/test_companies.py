"""Company ↔ branch split: a Company owns branch Organizations; HQ sees the chain."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Company, Organization, Role, User
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


@pytest.mark.django_db
def test_admin_creates_company(sys_admin: User) -> None:
    resp = _auth(sys_admin).post(
        "/api/companies/", {"name": "Umoja Pharma Group", "tin": "123456789"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert Company.objects.filter(name="Umoja Pharma Group").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="company").exists()


@pytest.mark.django_db
def test_non_admin_cannot_create_company(db: None) -> None:
    plain = User.objects.create_user(username="p", password="x")
    assert _auth(plain).post("/api/companies/", {"name": "X"}, format="json").status_code == 403


@pytest.mark.django_db
def test_branch_count_and_org_assignment(sys_admin: User) -> None:
    company = Company.objects.create(name="Group")
    hq = Organization.objects.create(name="HQ", type=Organization.OrgType.HQ, company=company)
    Organization.objects.create(name="Branch A", type=Organization.OrgType.RETAIL, company=company)
    resp = _auth(sys_admin).get(f"/api/companies/{company.pk}/")
    assert resp.status_code == 200
    assert resp.json()["branch_count"] == 2
    assert hq.company_id == company.pk


@pytest.mark.django_db
def test_cannot_delete_company_with_branches(sys_admin: User) -> None:
    company = Company.objects.create(name="Group")
    Organization.objects.create(name="Branch", type=Organization.OrgType.RETAIL, company=company)
    resp = _auth(sys_admin).delete(f"/api/companies/{company.pk}/")
    assert resp.status_code == 400
    assert Company.objects.filter(pk=company.pk).exists()


@pytest.mark.django_db
def test_org_admin_sees_only_own_company(db: None) -> None:
    mine = Company.objects.create(name="Mine")
    theirs = Company.objects.create(name="Theirs")
    hq = Organization.objects.create(name="My HQ", type=Organization.OrgType.HQ, company=mine)
    admin = User.objects.create_user(username="mgr", password="x", organization=hq)
    admin.roles.add(Role.objects.get(code="ORG_ADMIN"))
    resp = _auth(admin).get("/api/companies/")
    names = {c["name"] for c in resp.json()["results"]}
    assert names == {"Mine"} and "Theirs" not in names
    assert Company.objects.filter(name=theirs.name).exists()  # exists, just not visible


@pytest.mark.django_db
def test_hq_user_sees_all_company_branches(db: None) -> None:
    from apps.iam.scoping import organizations_visible_to

    company = Company.objects.create(name="Chain")
    hq = Organization.objects.create(name="HQ", type=Organization.OrgType.HQ, company=company)
    branch = Organization.objects.create(
        name="Branch", type=Organization.OrgType.RETAIL, company=company
    )
    outside = Organization.objects.create(name="Outside", type=Organization.OrgType.RETAIL)
    hq_user = User.objects.create_user(username="hq", password="x", organization=hq)
    visible = set(organizations_visible_to(hq_user).values_list("pk", flat=True))
    assert visible == {hq.pk, branch.pk}
    assert outside.pk not in visible


@pytest.mark.django_db
def test_branch_user_sees_only_itself(db: None) -> None:
    from apps.iam.scoping import organizations_visible_to

    company = Company.objects.create(name="Chain")
    Organization.objects.create(name="HQ", type=Organization.OrgType.HQ, company=company)
    branch = Organization.objects.create(
        name="Branch", type=Organization.OrgType.RETAIL, company=company
    )
    branch_user = User.objects.create_user(username="b", password="x", organization=branch)
    visible = set(organizations_visible_to(branch_user).values_list("pk", flat=True))
    assert visible == {branch.pk}
