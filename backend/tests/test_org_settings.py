"""Per-tenant org settings: plan, branding, and feature flags (admin-managed)."""

from __future__ import annotations

import pytest
from apps.iam.models import Organization, Role, User
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
def test_defaults(retail: Organization) -> None:
    assert retail.plan == "STANDARD"
    assert retail.brand_color == ""
    assert retail.feature_flags == {}


@pytest.mark.django_db
def test_admin_updates_plan_branding_and_flags(sys_admin: User, retail: Organization) -> None:
    resp = _auth(sys_admin).patch(
        f"/api/organizations/{retail.pk}/",
        {
            "plan": "PREMIUM",
            "brand_color": "#0D9488",
            "feature_flags": {"online_store": True, "insurance": False},
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    retail.refresh_from_db()
    assert retail.plan == "PREMIUM"
    assert retail.brand_color == "#0D9488"
    assert retail.feature_flags == {"online_store": True, "insurance": False}


@pytest.mark.django_db
def test_settings_are_serialized(sys_admin: User, retail: Organization) -> None:
    retail.plan = "BASIC"
    retail.feature_flags = {"loyalty": True}
    retail.save()
    body = _auth(sys_admin).get(f"/api/organizations/{retail.pk}/").json()
    assert body["plan"] == "BASIC"
    assert body["feature_flags"] == {"loyalty": True}


@pytest.mark.django_db
def test_non_admin_cannot_change_settings(retail: Organization) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    resp = _auth(plain).patch(
        f"/api/organizations/{retail.pk}/", {"plan": "PREMIUM"}, format="json"
    )
    assert resp.status_code == 403
    retail.refresh_from_db()
    assert retail.plan == "STANDARD"


@pytest.mark.django_db
def test_org_admin_cannot_change_other_org(org_admin: User, other: Organization) -> None:
    resp = _auth(org_admin).patch(
        f"/api/organizations/{other.pk}/", {"plan": "PREMIUM"}, format="json"
    )
    assert resp.status_code in (403, 404)
    other.refresh_from_db()
    assert other.plan == "STANDARD"
