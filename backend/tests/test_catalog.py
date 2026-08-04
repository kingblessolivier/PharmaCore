"""Catalog: product CRUD (admin-gated + audited), read for all, search."""

from __future__ import annotations

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def clerk(db: None) -> User:
    return User.objects.create_user(username="clerk", password="x")


@pytest.fixture
def paracetamol(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


@pytest.mark.django_db
def test_any_authed_user_can_list_products(clerk: User, paracetamol: Product) -> None:
    resp = _auth(clerk).get("/api/catalog/products/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.django_db
def test_non_admin_cannot_create_product(clerk: User) -> None:
    resp = _auth(clerk).post(
        "/api/catalog/products/", {"generic_name": "Amoxicillin"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_creates_product_and_audits(admin: User) -> None:
    resp = _auth(admin).post(
        "/api/catalog/products/",
        {"generic_name": "Amoxicillin", "strength": "500mg", "tax_class": "B"},
        format="json",
    )
    assert resp.status_code == 201
    assert Product.objects.filter(generic_name="Amoxicillin").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="product").exists()


@pytest.mark.django_db
def test_admin_updates_and_deletes_product(admin: User, paracetamol: Product) -> None:
    client = _auth(admin)
    up = client.patch(
        f"/api/catalog/products/{paracetamol.pk}/", {"reorder_level": 20}, format="json"
    )
    assert up.status_code == 200
    paracetamol.refresh_from_db()
    assert paracetamol.reorder_level == 20

    dele = client.delete(f"/api/catalog/products/{paracetamol.pk}/")
    assert dele.status_code == 204
    assert not Product.objects.filter(pk=paracetamol.pk).exists()
    assert AuditLog.objects.filter(action="DELETE", entity_type="product").exists()


@pytest.mark.django_db
def test_product_search(clerk: User) -> None:
    Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    Product.objects.create(generic_name="Paracetamol", strength="500mg")
    resp = _auth(clerk).get("/api/catalog/products/?search=amox")
    assert resp.status_code == 200
    names = [p["generic_name"] for p in resp.json()["results"]]
    assert names == ["Amoxicillin"]
