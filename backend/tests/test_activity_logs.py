"""Activity logs: org-scoped audit read, admin-only, login-failure logging."""

from __future__ import annotations

import pytest
from apps.iam.audit import record_audit
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
    return Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.mark.django_db
def test_org_scoped_logs(sys_admin: User, retail: Organization, other: Organization) -> None:
    record_audit(action="CREATE", organization=retail, entity_type="thing", entity_id="1")
    record_audit(action="CREATE", organization=other, entity_type="thing", entity_id="2")
    resp = _auth(sys_admin).get(f"/api/audit-logs/?organization={retail.pk}")
    assert resp.status_code == 200
    ids = {row["entity_id"] for row in resp.json()["results"]}
    assert ids == {"1"}


@pytest.mark.django_db
def test_audit_logs_admin_only(retail: Organization) -> None:
    plain = User.objects.create_user(username="plain", password="x", organization=retail)
    assert _auth(plain).get("/api/audit-logs/").status_code == 403


@pytest.mark.django_db
def test_org_admin_sees_only_own_org_logs(retail: Organization, other: Organization) -> None:
    mgr = User.objects.create_user(username="mgr", password="x", organization=retail)
    mgr.roles.add(Role.objects.get(code="ORG_ADMIN"))
    record_audit(action="X", organization=retail, entity_id="mine")
    record_audit(action="X", organization=other, entity_id="theirs")
    resp = _auth(mgr).get("/api/audit-logs/")
    ids = {row["entity_id"] for row in resp.json()["results"]}
    assert "mine" in ids and "theirs" not in ids


@pytest.mark.django_db
def test_failed_login_is_logged(retail: Organization) -> None:
    User.objects.create_user(username="alice", password="right-pass", organization=retail)
    client = APIClient()
    resp = client.post("/api/auth/login", {"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert AuditLog.objects.filter(action="LOGIN_FAILED").exists()
