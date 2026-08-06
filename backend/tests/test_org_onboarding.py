"""Organisation onboarding: activation gate + compliance documents (verify), audited."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, OrganizationDocument, Role, User
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


# --- activation gate -------------------------------------------------------


@pytest.mark.django_db
def test_new_org_defaults_active_but_can_be_suspended(
    sys_admin: User, retail: Organization
) -> None:
    assert retail.onboarding_status == "ACTIVE"
    resp = _auth(sys_admin).post(f"/api/organizations/{retail.pk}/suspend/")
    assert resp.status_code == 200, resp.content
    retail.refresh_from_db()
    assert retail.onboarding_status == "SUSPENDED" and retail.is_active is False
    assert AuditLog.objects.filter(action="ORG_SUSPEND").exists()


@pytest.mark.django_db
def test_activate_reopens_org(sys_admin: User, retail: Organization) -> None:
    retail.onboarding_status = "SUSPENDED"
    retail.is_active = False
    retail.save()
    resp = _auth(sys_admin).post(f"/api/organizations/{retail.pk}/activate/")
    assert resp.status_code == 200
    retail.refresh_from_db()
    assert retail.onboarding_status == "ACTIVE" and retail.is_active is True
    assert AuditLog.objects.filter(action="ORG_ACTIVATE").exists()


@pytest.mark.django_db
def test_org_admin_cannot_activate_other_org(org_admin: User, other: Organization) -> None:
    resp = _auth(org_admin).post(f"/api/organizations/{other.pk}/activate/")
    # Out of scope: the org isn't even visible, so it's 404 (or 403) — never allowed.
    assert resp.status_code in (403, 404)
    other.refresh_from_db()
    assert other.onboarding_status == "ACTIVE"  # unchanged


# --- compliance documents --------------------------------------------------


@pytest.mark.django_db
def test_admin_adds_and_verifies_org_document(sys_admin: User, retail: Organization) -> None:
    resp = _auth(sys_admin).post(
        "/api/organization-documents/",
        {
            "organization": retail.pk,
            "doc_type": "RWANDA_FDA_LICENCE",
            "document_number": "FDA-9931",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    doc = OrganizationDocument.objects.get(organization=retail, doc_type="RWANDA_FDA_LICENCE")
    assert AuditLog.objects.filter(action="CREATE", entity_type="organization_document").exists()

    v = _auth(sys_admin).post(f"/api/organization-documents/{doc.pk}/verify/")
    assert v.status_code == 200
    doc.refresh_from_db()
    assert doc.is_verified and doc.verified_by_id == sys_admin.pk
    assert AuditLog.objects.filter(action="VERIFY", entity_type="organization_document").exists()


@pytest.mark.django_db
def test_documents_filtered_by_org(
    sys_admin: User, retail: Organization, other: Organization
) -> None:
    OrganizationDocument.objects.create(organization=retail, doc_type="RDB_CERTIFICATE")
    OrganizationDocument.objects.create(organization=other, doc_type="RRA_VAT")
    resp = _auth(sys_admin).get(f"/api/organization-documents/?organization={retail.pk}")
    results = resp.json()["results"]
    assert len(results) == 1 and results[0]["doc_type"] == "RDB_CERTIFICATE"


@pytest.mark.django_db
def test_non_admin_cannot_access_org_documents(retail: Organization) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    assert _auth(plain).get("/api/organization-documents/").status_code == 403


@pytest.mark.django_db
def test_org_admin_scoped_to_own_org_documents(
    org_admin: User, retail: Organization, other: Organization
) -> None:
    OrganizationDocument.objects.create(organization=retail, doc_type="RDB_CERTIFICATE")
    OrganizationDocument.objects.create(organization=other, doc_type="RDB_CERTIFICATE")
    resp = _auth(org_admin).get("/api/organization-documents/")
    orgs = {
        OrganizationDocument.objects.get(pk=r["id"]).organization_id for r in resp.json()["results"]
    }
    assert orgs == {retail.pk}
