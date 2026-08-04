"""Licences: org-scoped, admin-gated, audited, expiry days."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, License, Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central", type=Organization.OrgType.RETAIL)


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.mark.django_db
def test_admin_adds_licence_and_audits(admin: User, retail: Organization) -> None:
    resp = _auth(admin).post(
        "/api/licenses/",
        {
            "organization": retail.pk,
            "license_type": "PREMISES",
            "license_number": "FDA-2024-001",
            "expiry_date": "2027-12-31",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert License.objects.filter(license_number="FDA-2024-001").exists()
    assert resp.json()["days_to_expiry"] is not None
    assert AuditLog.objects.filter(action="CREATE", entity_type="license").exists()


@pytest.mark.django_db
def test_non_admin_cannot_add_licence(retail: Organization) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    resp = _auth(plain).post(
        "/api/licenses/",
        {"organization": retail.pk, "license_type": "PREMISES", "license_number": "X"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_licences_scoped_by_org(admin: User, retail: Organization) -> None:
    other = Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)
    License.objects.create(organization=retail, license_type="PREMISES", license_number="A")
    License.objects.create(organization=other, license_type="PREMISES", license_number="B")
    resp = _auth(admin).get(f"/api/licenses/?organization={retail.pk}")
    nums = {row["license_number"] for row in resp.json()["results"]}
    assert nums == {"A"}
