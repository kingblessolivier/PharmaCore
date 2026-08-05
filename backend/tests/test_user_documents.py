"""User identity documents: admin-captured, org-scoped, verifiable, audited."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, Role, User, UserDocument
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="City Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def other(db: None) -> Organization:
    return Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)


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
def test_admin_adds_document_to_user(sys_admin: User, retail: Organization) -> None:
    staff = User.objects.create_user(username="cash", password="x", organization=retail)
    resp = _auth(sys_admin).post(
        "/api/user-documents/",
        {"user": staff.pk, "doc_type": "NATIONAL_ID", "document_number": "119900123"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert UserDocument.objects.filter(user=staff, doc_type="NATIONAL_ID").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="user_document").exists()


@pytest.mark.django_db
def test_documents_filtered_by_user(sys_admin: User, retail: Organization) -> None:
    a = User.objects.create_user(username="a", password="x", organization=retail)
    b = User.objects.create_user(username="b", password="x", organization=retail)
    UserDocument.objects.create(user=a, doc_type="NATIONAL_ID")
    UserDocument.objects.create(user=b, doc_type="PASSPORT")
    resp = _auth(sys_admin).get(f"/api/user-documents/?user={a.pk}")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1 and results[0]["doc_type"] == "NATIONAL_ID"


@pytest.mark.django_db
def test_verify_document(sys_admin: User, retail: Organization) -> None:
    staff = User.objects.create_user(username="cash", password="x", organization=retail)
    doc = UserDocument.objects.create(user=staff, doc_type="PROFESSIONAL_LICENCE")
    resp = _auth(sys_admin).post(f"/api/user-documents/{doc.pk}/verify/")
    assert resp.status_code == 200
    doc.refresh_from_db()
    assert doc.is_verified and doc.verified_by_id == sys_admin.pk
    assert AuditLog.objects.filter(action="VERIFY", entity_type="user_document").exists()


@pytest.mark.django_db
def test_non_admin_cannot_access(retail: Organization) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    assert _auth(plain).get("/api/user-documents/").status_code == 403


@pytest.mark.django_db
def test_org_admin_scoped_to_own_org(
    org_admin: User, retail: Organization, other: Organization
) -> None:
    mine = User.objects.create_user(username="mine", password="x", organization=retail)
    theirs = User.objects.create_user(username="theirs", password="x", organization=other)
    UserDocument.objects.create(user=mine, doc_type="NATIONAL_ID")
    UserDocument.objects.create(user=theirs, doc_type="NATIONAL_ID")
    resp = _auth(org_admin).get("/api/user-documents/")
    users = {UserDocument.objects.get(pk=r["id"]).user.username for r in resp.json()["results"]}
    assert users == {"mine"}


@pytest.mark.django_db
def test_org_admin_cannot_add_doc_to_outside_user(org_admin: User, other: Organization) -> None:
    outsider = User.objects.create_user(username="out", password="x", organization=other)
    resp = _auth(org_admin).post(
        "/api/user-documents/", {"user": outsider.pk, "doc_type": "PASSPORT"}, format="json"
    )
    assert resp.status_code == 403
