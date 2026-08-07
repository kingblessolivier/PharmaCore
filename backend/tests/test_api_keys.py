"""Service-account API keys: created once, authenticate as their user, revocable."""

from __future__ import annotations

import pytest
from apps.iam.models import ApiKey, AuditLog, Organization, Role, User
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
def service(retail: Organization) -> User:
    u = User.objects.create_user(username="svc", password="x", organization=retail)
    u.roles.add(Role.objects.get(code="PHARMACIST"))
    return u


@pytest.mark.django_db
def test_create_returns_raw_key_once(sys_admin: User, service: User) -> None:
    resp = _auth(sys_admin).post(
        "/api/api-keys/", {"name": "EBM bridge", "user": service.pk}, format="json"
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["key"].startswith("pk_")
    assert body["prefix"] == body["key"][:12]
    # only the hash is stored, never the raw key
    key = ApiKey.objects.get(pk=body["id"])
    assert key.key_hash and key.key_hash != body["key"]
    assert AuditLog.objects.filter(action="API_KEY_CREATE").exists()


@pytest.mark.django_db
def test_key_authenticates_as_its_user(sys_admin: User, service: User) -> None:
    raw = (
        _auth(sys_admin)
        .post("/api/api-keys/", {"name": "k", "user": service.pk}, format="json")
        .json()["key"]
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "svc"  # acts as the service account


@pytest.mark.django_db
def test_revoked_key_rejected(sys_admin: User, service: User) -> None:
    created = (
        _auth(sys_admin)
        .post("/api/api-keys/", {"name": "k", "user": service.pk}, format="json")
        .json()
    )
    raw = created["key"]
    _auth(sys_admin).delete(f"/api/api-keys/{created['id']}/")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw)
    assert client.get("/api/auth/me").status_code == 401
    assert AuditLog.objects.filter(action="API_KEY_REVOKE").exists()


@pytest.mark.django_db
def test_bad_key_rejected(db: None) -> None:
    client = APIClient()
    client.credentials(HTTP_X_API_KEY="pk_not-a-real-key")
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
def test_non_admin_cannot_manage_keys(service: User) -> None:
    assert _auth(service).get("/api/api-keys/").status_code == 403


@pytest.mark.django_db
def test_org_admin_cannot_key_for_outside_user(retail: Organization, other: Organization) -> None:
    org_admin = User.objects.create_user(username="mgr", password="x", organization=retail)
    org_admin.roles.add(Role.objects.get(code="ORG_ADMIN"))
    outsider = User.objects.create_user(username="out", password="x", organization=other)
    resp = _auth(org_admin).post(
        "/api/api-keys/", {"name": "k", "user": outsider.pk}, format="json"
    )
    assert resp.status_code == 403
