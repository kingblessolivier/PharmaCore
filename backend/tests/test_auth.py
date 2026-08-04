"""Auth: a user can log in (JWT) and read their profile — Phase 0 exit criterion."""

from __future__ import annotations

import pytest
from apps.iam.models import AuditLog, User
from rest_framework.test import APIClient


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(username="alice", password="s3cret-pass", email="a@x.rw")


@pytest.mark.django_db
def test_login_returns_tokens_and_audits(user: User) -> None:
    client = APIClient()
    resp = client.post("/api/auth/login", {"username": "alice", "password": "s3cret-pass"})
    assert resp.status_code == 200
    assert "access" in resp.json() and "refresh" in resp.json()
    # login is recorded in the append-only audit log
    assert AuditLog.objects.filter(action="LOGIN", user=user).exists()


@pytest.mark.django_db
def test_login_bad_credentials(user: User) -> None:
    client = APIClient()
    resp = client.post("/api/auth/login", {"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_me_requires_auth(user: User) -> None:
    client = APIClient()
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
def test_me_returns_profile(user: User) -> None:
    client = APIClient()
    tokens = client.post("/api/auth/login", {"username": "alice", "password": "s3cret-pass"}).json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
