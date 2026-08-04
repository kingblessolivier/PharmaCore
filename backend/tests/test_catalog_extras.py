"""Catalog extras: suppliers, ingredients, product barcodes — admin-gated, audited."""

from __future__ import annotations

import pytest
from apps.catalog.models import ActiveIngredient, Product, ProductBarcode
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
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


@pytest.mark.django_db
def test_admin_creates_supplier_audited(admin: User) -> None:
    resp = _auth(admin).post(
        "/api/catalog/suppliers/", {"name": "MedImport Ltd", "lead_time_days": 7}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert AuditLog.objects.filter(action="CREATE", entity_type="supplier").exists()


@pytest.mark.django_db
def test_non_admin_cannot_create_supplier(db: None) -> None:
    plain = User.objects.create_user(username="p", password="x")
    resp = _auth(plain).post("/api/catalog/suppliers/", {"name": "X"}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_product_ingredient_scoped(admin: User, product: Product) -> None:
    ing = ActiveIngredient.objects.create(name="Amoxicillin")
    resp = _auth(admin).post(
        "/api/catalog/product-ingredients/",
        {"product": product.pk, "ingredient": ing.pk, "amount": "500mg"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    listed = _auth(admin).get(f"/api/catalog/product-ingredients/?product={product.pk}")
    assert listed.json()["count"] == 1


@pytest.mark.django_db
def test_product_barcode_unique(admin: User, product: Product) -> None:
    client = _auth(admin)
    body = {"product": product.pk, "barcode": "5901234123457", "packaging_level": "EACH"}
    assert client.post("/api/catalog/product-barcodes/", body, format="json").status_code == 201
    dup = client.post("/api/catalog/product-barcodes/", body, format="json")
    assert dup.status_code == 400
    assert ProductBarcode.objects.filter(product=product).count() == 1
