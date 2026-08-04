"""Pharmacy catalog (PharmacyProduct): org-scoped listing + price, admin-gated, audited."""

from __future__ import annotations

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import PharmacyProduct
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central", type=Organization.OrgType.RETAIL)


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg")


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.mark.django_db
def test_admin_adds_product_to_pharmacy(
    sys_admin: User, retail: Organization, product: Product
) -> None:
    resp = _auth(sys_admin).post(
        "/api/inventory/pharmacy-products/",
        {
            "organization": retail.pk,
            "product": product.pk,
            "retail_price": "1200.00",
            "min_stock_level": 10,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert PharmacyProduct.objects.filter(organization=retail, product=product).exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="pharmacy_product").exists()


@pytest.mark.django_db
def test_non_admin_cannot_add(retail: Organization, product: Product) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    resp = _auth(plain).post(
        "/api/inventory/pharmacy-products/",
        {"organization": retail.pk, "product": product.pk},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_unique_per_pharmacy(sys_admin: User, retail: Organization, product: Product) -> None:
    client = _auth(sys_admin)
    body = {"organization": retail.pk, "product": product.pk}
    assert client.post("/api/inventory/pharmacy-products/", body, format="json").status_code == 201
    dup = client.post("/api/inventory/pharmacy-products/", body, format="json")
    assert dup.status_code == 400  # unique constraint


@pytest.mark.django_db
def test_list_scoped_by_organization(
    sys_admin: User, retail: Organization, product: Product
) -> None:
    other = Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)
    PharmacyProduct.objects.create(organization=retail, product=product)
    PharmacyProduct.objects.create(organization=other, product=product)
    resp = _auth(sys_admin).get(f"/api/inventory/pharmacy-products/?organization={retail.pk}")
    assert resp.json()["count"] == 1
