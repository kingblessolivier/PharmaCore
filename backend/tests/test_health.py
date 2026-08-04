"""Phase 0 smoke tests — the API boots and reports healthy."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_ok(client: Client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert "version" in body
    assert "environment" in body


@pytest.mark.django_db
def test_root_banner(client: Client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["docs"] == "/api/docs/"
