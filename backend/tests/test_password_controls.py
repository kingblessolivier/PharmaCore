"""Password controls: admin reset (force-change) + self-service change, strength-checked."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="City Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="Str0ng-Admin-Pw")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def staff(retail: Organization) -> User:
    return User.objects.create_user(
        username="cash", password="Old-Passw0rd-99", organization=retail
    )


# --- admin reset -----------------------------------------------------------


@pytest.mark.django_db
def test_admin_resets_password_and_forces_change(sys_admin: User, staff: User) -> None:
    resp = _auth(sys_admin).post(
        f"/api/users/{staff.pk}/set-password/", {"password": "Brand-New-Pw-123"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    staff.refresh_from_db()
    assert staff.check_password("Brand-New-Pw-123")
    assert staff.must_change_password is True
    assert AuditLog.objects.filter(action="PASSWORD_RESET").exists()


@pytest.mark.django_db
def test_reset_rejects_weak_password(sys_admin: User, staff: User) -> None:
    resp = _auth(sys_admin).post(
        f"/api/users/{staff.pk}/set-password/", {"password": "123"}, format="json"
    )
    assert resp.status_code == 400  # too short / too common


@pytest.mark.django_db
def test_non_admin_cannot_reset(staff: User, retail: Organization) -> None:
    plain = User.objects.create_user(username="p", password="Some-Passw0rd", organization=retail)
    resp = _auth(plain).post(
        f"/api/users/{staff.pk}/set-password/", {"password": "Brand-New-Pw-123"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_cannot_reset_own_via_admin_endpoint(sys_admin: User) -> None:
    resp = _auth(sys_admin).post(
        f"/api/users/{sys_admin.pk}/set-password/", {"password": "Another-Pw-123"}, format="json"
    )
    assert resp.status_code == 400  # must use change-password for self


# --- self-service change ---------------------------------------------------


@pytest.mark.django_db
def test_user_changes_own_password(staff: User) -> None:
    resp = _auth(staff).post(
        "/api/auth/change-password",
        {"old_password": "Old-Passw0rd-99", "new_password": "My-New-Passw0rd-1"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    staff.refresh_from_db()
    assert staff.check_password("My-New-Passw0rd-1")
    assert staff.must_change_password is False
    assert AuditLog.objects.filter(action="PASSWORD_CHANGE").exists()


@pytest.mark.django_db
def test_change_rejects_wrong_old_password(staff: User) -> None:
    resp = _auth(staff).post(
        "/api/auth/change-password",
        {"old_password": "wrong", "new_password": "My-New-Passw0rd-1"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_change_rejects_weak_new_password(staff: User) -> None:
    resp = _auth(staff).post(
        "/api/auth/change-password",
        {"old_password": "Old-Passw0rd-99", "new_password": "123"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_me_exposes_must_change_password(staff: User) -> None:
    staff.must_change_password = True
    staff.save()
    client = APIClient()
    tokens = client.post(
        "/api/auth/login", {"username": "cash", "password": "Old-Passw0rd-99"}
    ).json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.get("/api/auth/me").json()["must_change_password"] is True
