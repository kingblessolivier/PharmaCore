"""Catalog pricing & commercial tests: price lists, prices, formularies, UoM, substitutes."""

from __future__ import annotations

import pytest
from apps.catalog.models import (
    FormularyItem,
    PriceList,
    Product,
    ProductPrice,
    ProductSubstitute,
    ProductUomConversion,
)
from apps.iam.models import AuditLog, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="pricing_admin", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg")


@pytest.fixture
def alt_product(db: None) -> Product:
    return Product.objects.create(generic_name="Ibuprofen", strength="400mg")


@pytest.mark.django_db
def test_price_list_and_product_price(admin: User, product: Product) -> None:
    client = _auth(admin)
    pl_resp = client.post(
        "/api/catalog/price-lists/",
        {"name": "Retail 2026", "list_type": "RETAIL"},
        format="json",
    )
    assert pl_resp.status_code == 201
    pl_id = pl_resp.json()["id"]

    pr_resp = client.post(
        "/api/catalog/product-prices/",
        {"price_list": pl_id, "product": product.pk, "unit_price": "150.00", "min_quantity": 1},
        format="json",
    )
    assert pr_resp.status_code == 201
    assert ProductPrice.objects.filter(price_list_id=pl_id, unit_price=150.00).exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="product_price").exists()


@pytest.mark.django_db
def test_formulary_item(admin: User, product: Product) -> None:
    client = _auth(admin)
    resp = client.post(
        "/api/catalog/formulary-items/",
        {
            "scheme_name": "RSSB / RAMA",
            "product": product.pk,
            "is_covered": True,
            "max_reimbursable_price": "120.00",
            "copay_percentage": "15.00",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert FormularyItem.objects.filter(scheme_name="RSSB / RAMA").exists()


@pytest.mark.django_db
def test_product_uom_conversion(admin: User, product: Product) -> None:
    client = _auth(admin)
    resp = client.post(
        "/api/catalog/product-uom-conversions/",
        {
            "product": product.pk,
            "unit_name": "Strip",
            "conversion_factor": 10,
            "price_per_unit": "15.00",
            "is_default_dispensing": True,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert ProductUomConversion.objects.filter(unit_name="Strip").exists()


@pytest.mark.django_db
def test_product_substitute(admin: User, product: Product, alt_product: Product) -> None:
    client = _auth(admin)
    resp = client.post(
        "/api/catalog/product-substitutes/",
        {
            "product": product.pk,
            "substitute_product": alt_product.pk,
            "substitute_type": "THERAPEUTIC_ALTERNATIVE",
            "notes": "Analgesic alternative when NSAID is appropriate",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert ProductSubstitute.objects.filter(substitute_type="THERAPEUTIC_ALTERNATIVE").exists()
