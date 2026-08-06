"""Admin oversight: PF-number login, view-as impersonation, per-user activity."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, ImpersonationSession, Organization, Role, User
from rest_framework.test import APIClient


def _bearer(client: APIClient, token: str) -> None:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central", type=Organization.OrgType.RETAIL)


@pytest.fixture
def other(db: None) -> Organization:
    return Organization.objects.create(name="Musanze Branch", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="s3cret-pass")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def cashier(retail: Organization) -> User:
    u = User.objects.create_user(
        username="cash1", password="s3cret-pass", organization=retail, pf_number="PF-100"
    )
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


# --- PF-number login -------------------------------------------------------


@pytest.mark.django_db
def test_login_with_pf_number(cashier: User) -> None:
    resp = APIClient().post("/api/auth/login", {"username": "PF-100", "password": "s3cret-pass"})
    assert resp.status_code == 200, resp.content
    assert "access" in resp.json()
    assert AuditLog.objects.filter(action="LOGIN", user=cashier).exists()


@pytest.mark.django_db
def test_login_with_username_still_works(cashier: User) -> None:
    resp = APIClient().post("/api/auth/login", {"username": "cash1", "password": "s3cret-pass"})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_blank_pf_number_not_a_login(db: None) -> None:
    # A user with an empty pf_number must never be matchable by a blank identifier.
    User.objects.create_user(username="noemail", password="s3cret-pass")  # pf_number=""
    resp = APIClient().post("/api/auth/login", {"username": "", "password": "s3cret-pass"})
    assert resp.status_code >= 400  # rejected (400 validation / 401 auth), never a token
    assert "access" not in resp.json()


# --- View-as / impersonation ----------------------------------------------


@pytest.mark.django_db
def test_admin_can_view_as_user_and_is_audited(sys_admin: User, cashier: User) -> None:
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    resp = client.post("/api/auth/impersonate", {"user_id": cashier.pk}, format="json")
    assert resp.status_code == 200, resp.content
    token = resp.json()["access"]
    assert ImpersonationSession.objects.filter(admin=sys_admin, target=cashier).exists()
    assert AuditLog.objects.filter(action="IMPERSONATE_START", user=sys_admin).exists()

    # The token acts as the cashier, and /me exposes the impersonator banner data.
    imp = APIClient()
    _bearer(imp, token)
    me = imp.get("/api/auth/me")
    assert me.json()["username"] == "cash1"
    assert me.json()["impersonator"]["username"] == "root"


@pytest.mark.django_db
def test_stop_impersonation_closes_session(sys_admin: User, cashier: User) -> None:
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    token = client.post("/api/auth/impersonate", {"user_id": cashier.pk}, format="json").json()[
        "access"
    ]
    imp = APIClient()
    _bearer(imp, token)
    assert imp.post("/api/auth/impersonate/stop").status_code == 204
    session = ImpersonationSession.objects.get(admin=sys_admin, target=cashier)
    assert session.ended_at is not None
    assert AuditLog.objects.filter(action="IMPERSONATE_STOP").exists()


@pytest.mark.django_db
def test_cannot_view_as_self(sys_admin: User) -> None:
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    resp = client.post("/api/auth/impersonate", {"user_id": sys_admin.pk}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_cannot_view_as_another_admin(sys_admin: User, db: None) -> None:
    admin2 = User.objects.create_user(username="root2", password="x")
    admin2.roles.add(Role.objects.get(code="SYS_ADMIN"))
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    resp = client.post("/api/auth/impersonate", {"user_id": admin2.pk}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_non_admin_cannot_impersonate(cashier: User) -> None:
    client = APIClient()
    client.force_authenticate(user=cashier)
    resp = client.post("/api/auth/impersonate", {"user_id": cashier.pk}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_org_admin_cannot_view_as_user_in_other_org(
    retail: Organization, other: Organization
) -> None:
    org_admin = User.objects.create_user(username="mgr", password="x", organization=retail)
    org_admin.roles.add(Role.objects.get(code="ORG_ADMIN"))
    outsider = User.objects.create_user(username="outsider", password="x", organization=other)
    client = APIClient()
    client.force_authenticate(user=org_admin)
    resp = client.post("/api/auth/impersonate", {"user_id": outsider.pk}, format="json")
    assert resp.status_code == 403


# --- Per-user activity -----------------------------------------------------


@pytest.mark.django_db
def test_user_activity_returns_recent_and_counts(sys_admin: User, cashier: User) -> None:
    AuditLog.objects.create(user=cashier, action="LOGIN", entity_type="auth")
    AuditLog.objects.create(user=cashier, action="CREATE", entity_type="sale")
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    resp = client.get(f"/api/users/{cashier.pk}/activity/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["user"]["username"] == "cash1"
    assert body["counts"].get("LOGIN") == 1
    assert len(body["recent"]) == 2


@pytest.mark.django_db
def test_audit_logs_filter_by_user_and_action(sys_admin: User, cashier: User) -> None:
    AuditLog.objects.create(user=cashier, action="LOGIN", entity_type="auth")
    AuditLog.objects.create(user=sys_admin, action="CREATE", entity_type="user")
    client = APIClient()
    client.force_authenticate(user=sys_admin)
    resp = client.get(f"/api/audit-logs/?user={cashier.pk}&action=LOGIN")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1 and results[0]["action"] == "LOGIN"
