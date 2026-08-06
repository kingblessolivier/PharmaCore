"""Force-logout / session revocation via token_version."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, Organization, Role, User
from rest_framework.test import APIClient


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
    u = User.objects.create_user(username="cash", password="Old-Passw0rd-99", organization=retail)
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


def _login(username: str, password: str) -> dict:
    return APIClient().post(
        "/api/auth/login", {"username": username, "password": password}
    ).json()


@pytest.mark.django_db
def test_force_logout_revokes_existing_token(sys_admin: User, staff: User) -> None:
    tokens = _login("cash", "Old-Passw0rd-99")
    user_client = APIClient()
    user_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert user_client.get("/api/auth/me").status_code == 200  # works before

    admin = APIClient()
    admin.force_authenticate(user=sys_admin)
    assert admin.post(f"/api/users/{staff.pk}/force-logout/").status_code == 200
    staff.refresh_from_db()
    assert staff.token_version == 1
    assert AuditLog.objects.filter(action="FORCE_LOGOUT").exists()

    # The previously-issued token is now rejected.
    assert user_client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
def test_user_can_login_again_after_force_logout(sys_admin: User, staff: User) -> None:
    APIClient().post("/api/auth/login", {"username": "cash", "password": "Old-Passw0rd-99"})
    admin = APIClient()
    admin.force_authenticate(user=sys_admin)
    admin.post(f"/api/users/{staff.pk}/force-logout/")
    # A fresh login mints a token with the new version and works.
    tokens = _login("cash", "Old-Passw0rd-99")
    fresh = APIClient()
    fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert fresh.get("/api/auth/me").status_code == 200


@pytest.mark.django_db
def test_refreshed_token_still_revocable(sys_admin: User, staff: User) -> None:
    tokens = _login("cash", "Old-Passw0rd-99")
    # refresh to get a new access token (should still carry tv)
    refreshed = APIClient().post("/api/auth/refresh", {"refresh": tokens["refresh"]}).json()
    admin = APIClient()
    admin.force_authenticate(user=sys_admin)
    admin.post(f"/api/users/{staff.pk}/force-logout/")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed['access']}")
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
def test_non_admin_cannot_force_logout(staff: User) -> None:
    client = APIClient()
    client.force_authenticate(user=staff)
    assert client.post(f"/api/users/{staff.pk}/force-logout/").status_code == 403
