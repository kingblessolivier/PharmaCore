"""Selling a box, a strip, a tablet — and half of one where that is allowed.

The counter is where the unit chain earns its keep. A customer asks for "a box"
and the shelf must give up a hundred tablets; a customer asks for half a tablet
and the shelf must give up half, but only for a product a pharmacist has
approved for splitting.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductUnit
from apps.catalog.units import UnitError
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail.lines import build_line
from apps.retail.models import Sale
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def make_product(name="Paracetamol", divisibility=1):
    product = Product.objects.create(
        generic_name=name, strength="500mg", dosage_form="TABLET", divisibility=divisibility
    )
    ProductUnit.objects.create(
        product=product,
        code="TABLET",
        factor_to_base=1,
        level=0,
        is_base=True,
        is_sale_default=True,
    )
    ProductUnit.objects.create(
        product=product, code="STRIP", name="Strip of 10", factor_to_base=10, level=1
    )
    ProductUnit.objects.create(
        product=product, code="PACK", name="Box of 100", factor_to_base=100, level=2
    )
    return product


def stock(org, product, qty=1000):
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number="B1",
        expiry_date=timezone.localdate() + timedelta(days=365),
        quantity_available=Decimal(qty),
        wholesale_cost=Decimal("10"),
        status=InventoryBatch.Status.ACTIVE,
    )


def open_sale(org):
    return Sale.objects.create(
        organization=org, status=Sale.Status.OPEN, sale_number=f"S-{Sale.objects.count() + 1}"
    )


def test_selling_one_box_takes_a_hundred_tablets_off_the_shelf(org):
    """The defect this whole change exists to fix."""
    product = make_product()
    sale = open_sale(org)

    line = build_line(
        sale=sale,
        product=product,
        quantity=1,
        unit_code="PACK",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )

    assert line.quantity == Decimal("1.000")
    assert line.unit.code == "PACK"
    assert line.quantity_base == Decimal("100.000")


def test_a_strip_is_ten_tablets(org):
    product = make_product()
    line = build_line(
        sale=open_sale(org),
        product=product,
        quantity=3,
        unit_code="STRIP",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    assert line.quantity_base == Decimal("30.000")


def test_a_line_with_no_unit_stated_uses_the_sale_default(org):
    """An older client that sends no unit keeps behaving exactly as it did."""
    product = make_product()
    line = build_line(
        sale=open_sale(org),
        product=product,
        quantity=5,
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    assert line.unit.code == "TABLET"
    assert line.quantity_base == Decimal("5.000")


def test_the_pack_price_scales_from_the_tablet_price_when_none_is_set(org):
    product = make_product()
    line = build_line(
        sale=open_sale(org),
        product=product,
        quantity=1,
        unit_code="PACK",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    assert line.unit_price == Decimal("5000.00")


def test_a_pack_priced_in_its_own_right_beats_the_scaled_price(org):
    """A box is normally cheaper per tablet than the loose tablets from it."""
    product = make_product()
    pack = product.units.get(code="PACK")
    pack.price = Decimal("4200")
    pack.save(update_fields=["price"])

    line = build_line(
        sale=open_sale(org),
        product=product,
        quantity=1,
        unit_code="PACK",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    assert line.unit_price == Decimal("4200")


def test_half_a_tablet_is_refused_unless_the_product_is_approved(org):
    product = make_product()
    with pytest.raises(UnitError, match="whole only"):
        build_line(
            sale=open_sale(org),
            product=product,
            quantity="0.5",
            unit_code="TABLET",
            base_price=Decimal("50"),
            tax_rate=Decimal("0"),
        )


def test_half_a_tablet_is_sold_when_the_product_is_approved_for_halves(org):
    product = make_product("Warfarin", divisibility=2)
    line = build_line(
        sale=open_sale(org),
        product=product,
        quantity="0.5",
        unit_code="TABLET",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    assert line.quantity == Decimal("0.500")
    assert line.quantity_base == Decimal("0.500")


def test_a_unit_the_product_is_not_sold_in_is_refused(org):
    product = make_product()
    with pytest.raises(UnitError, match="not sold in"):
        build_line(
            sale=open_sale(org),
            product=product,
            quantity=1,
            unit_code="PALLET",
            base_price=Decimal("50"),
            tax_rate=Decimal("0"),
        )


def test_completing_a_box_sale_draws_a_hundred_from_the_batch(org):
    """End to end: the shelf, not just the line, must agree."""
    from apps.retail.services import complete_sale

    product = make_product()
    PharmacyProduct.objects.create(
        organization=org, product=product, retail_price=Decimal("50"), is_active=True
    )
    batch = stock(org, product, 1000)
    sale = open_sale(org)
    build_line(
        sale=sale,
        product=product,
        quantity=1,
        unit_code="PACK",
        base_price=Decimal("50"),
        tax_rate=Decimal("0"),
    )

    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "5000"}], user=None)

    batch.refresh_from_db()
    assert batch.quantity_available == Decimal("900.000"), "one box is a hundred tablets"


# ---------------------------------------------------------------------------
# What the till is actually sent, and what it gets back
# ---------------------------------------------------------------------------


def test_the_counter_search_offers_the_packaging_levels(org):
    """The till cannot offer a box unless the search says one exists."""
    from apps.iam.models import User
    from rest_framework.test import APIClient

    product = make_product()
    PharmacyProduct.objects.create(
        organization=org, product=product, retail_price=Decimal("50"), is_active=True
    )
    stock(org, product, 500)
    user = User.objects.create_superuser(username="till", password="pw", organization=org)
    client = APIClient()
    client.force_authenticate(user=user)

    body = client.get(f"/api/retail/counter/search/?organization={org.pk}&q=Para").json()
    assert body["results"], body
    hit = body["results"][0]

    levels = {u["code"]: u for u in hit["sale_units"]}
    assert set(levels) == {"TABLET", "STRIP", "PACK"}
    # A box of 100 costs a hundred tablets' worth unless priced in its own right.
    assert levels["PACK"]["unit_price"] == "5000.00"
    assert levels["TABLET"]["is_default"] is True
    assert hit["divisibility"] == 1
