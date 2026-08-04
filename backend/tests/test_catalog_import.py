"""Bulk CSV import for the product catalog (admin-only, upsert)."""

from __future__ import annotations

import pytest
from apps.catalog.models import Product
from apps.iam.models import Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.mark.django_db
def test_import_creates_then_updates(admin: User) -> None:
    rows = [
        {
            "generic_name": "Paracetamol",
            "strength": "500mg",
            "dosage_form": "TABLET",
            "tax_class": "B",
            "requires_prescription": "false",
            "units_per_pack": "100",
        },
        {"generic_name": "", "strength": "x"},  # invalid → skipped
    ]
    resp = _auth(admin).post("/api/catalog/products/import/", {"rows": rows}, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["created"] == 1 and body["updated"] == 0
    assert len(body["errors"]) == 1
    p = Product.objects.get(generic_name="Paracetamol", strength="500mg")
    assert p.units_per_pack == 100

    # Re-import same product with a new pack → update, not duplicate.
    rows[0]["units_per_pack"] = "50"
    resp2 = _auth(admin).post("/api/catalog/products/import/", {"rows": [rows[0]]}, format="json")
    assert resp2.json() == {"created": 0, "updated": 1, "errors": []}
    assert Product.objects.filter(generic_name="Paracetamol", strength="500mg").count() == 1
    p.refresh_from_db()
    assert p.units_per_pack == 50


@pytest.mark.django_db
def test_import_requires_admin(db: None) -> None:
    plain = User.objects.create_user(username="p", password="x")
    resp = _auth(plain).post(
        "/api/catalog/products/import/", {"rows": [{"generic_name": "X"}]}, format="json"
    )
    assert resp.status_code == 403
