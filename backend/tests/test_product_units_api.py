"""Managing a product's packaging chain from the catalogue screen.

The model and the conversion service landed first; without a way to record a
chain they govern nothing, which is the exact failure mode that left
ProductUomConversion with zero rows and no readers for a year.

The database constraints are the real guarantee. These check the screen gets a
sentence it can show a person instead of an IntegrityError.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductUnit
from apps.iam.models import Organization, User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

URL = "/api/catalog/product-units/"


@pytest.fixture
def admin():
    org = Organization.objects.create(name="HQ", type="HQ")
    return User.objects.create_superuser(username="root", password="pw", organization=org)


@pytest.fixture
def client(admin):
    api = APIClient()
    api.force_authenticate(user=admin)
    return api


@pytest.fixture
def product():
    return Product.objects.create(
        generic_name="Paracetamol", strength="500mg", dosage_form="TABLET"
    )


def base_unit(product):
    return ProductUnit.objects.create(
        product=product, code="TABLET", factor_to_base=1, level=0, is_base=True
    )


def test_a_chain_can_be_recorded(client, product):
    base_unit(product)
    resp = client.post(
        URL,
        {
            "product": product.pk,
            "code": "PACK",
            "name": "Box of 100",
            "factor_to_base": "100",
            "level": 2,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert product.units.get(code="PACK").factor_to_base == Decimal("100.000")


def test_a_second_base_unit_is_refused_in_words(client, product):
    """Not an IntegrityError — the screen has to be able to say what is wrong."""
    base_unit(product)
    resp = client.post(
        URL,
        {"product": product.pk, "code": "CAPSULE", "factor_to_base": "1", "is_base": True},
        format="json",
    )
    assert resp.status_code == 400
    assert "already has a base unit" in str(resp.content)


def test_a_base_unit_must_measure_one_of_itself(client, product):
    resp = client.post(
        URL,
        {"product": product.pk, "code": "PACK", "factor_to_base": "100", "is_base": True},
        format="json",
    )
    assert resp.status_code == 400
    assert "one of itself" in str(resp.content)


def test_the_base_unit_has_to_come_first(client, product):
    """A level above the base means nothing until there is a base to measure against."""
    resp = client.post(
        URL, {"product": product.pk, "code": "PACK", "factor_to_base": "1"}, format="json"
    )
    assert resp.status_code == 400
    assert "base unit first" in str(resp.content)


def test_only_one_sale_default(client, product):
    base = base_unit(product)
    base.is_sale_default = True
    base.save(update_fields=["is_sale_default"])

    resp = client.post(
        URL,
        {
            "product": product.pk,
            "code": "PACK",
            "factor_to_base": "100",
            "is_sale_default": True,
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "one sale unit" in str(resp.content)


def test_the_chain_is_listed_for_one_product(client, product):
    base_unit(product)
    ProductUnit.objects.create(product=product, code="PACK", factor_to_base=100, level=2)
    other = Product.objects.create(generic_name="Amoxicillin", dosage_form="CAPSULE")
    ProductUnit.objects.create(product=other, code="CAPSULE", factor_to_base=1, is_base=True)

    rows = client.get(f"{URL}?product={product.pk}").json()
    results = rows["results"] if isinstance(rows, dict) else rows
    assert {r["code"] for r in results} == {"TABLET", "PACK"}


def test_a_unit_carries_its_own_barcode(client, product):
    """Under GS1 each packaging level has its own GTIN, so a scanner can tell a
    case from the pack inside it."""
    base_unit(product)
    resp = client.post(
        URL,
        {
            "product": product.pk,
            "code": "CASE",
            "factor_to_base": "2400",
            "level": 3,
            "barcode": "05012345678900",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert product.units.get(code="CASE").barcode == "05012345678900"


def test_divisibility_is_editable_on_the_product(client, product):
    """Only a pharmacist can say a tablet may be halved, so it must be settable."""
    resp = client.patch(
        f"/api/catalog/products/{product.pk}/",
        {"divisibility": 2, "split_note": "Scored, immediate release."},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    product.refresh_from_db()
    assert product.divisibility == 2
