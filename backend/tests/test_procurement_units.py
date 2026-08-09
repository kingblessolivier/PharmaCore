"""Buying in cartons and receiving tablets.

Procurement was the last place a quantity carried no unit. Ordering "10" from a
supplier who trades in cartons put ten tablets on the shelf instead of the
24,000 the cartons held — and because the cost was carried per *ordered* unit
too, inventory was overstated by the same factor in the opposite direction.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductUnit, Supplier
from apps.iam.models import Organization
from apps.procurement.models import PurchaseOrder, PurchaseOrderLine
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def paracetamol():
    product = Product.objects.create(
        generic_name="Paracetamol", strength="500mg", dosage_form="TABLET"
    )
    ProductUnit.objects.create(product=product, code="TABLET", factor_to_base=1, is_base=True)
    ProductUnit.objects.create(
        product=product, code="PACK", name="Box of 100", factor_to_base=100, level=2
    )
    ProductUnit.objects.create(
        product=product, code="CARTON", name="Carton of 24 boxes", factor_to_base=2400, level=3
    )
    return product


def order_for(org, product, *, unit_code, quantity, price):
    supplier = Supplier.objects.create(name="Global Pharma Imports")
    order = PurchaseOrder.objects.create(
        organization=org,
        supplier=supplier,
        po_number=f"PO-{PurchaseOrder.objects.count() + 1:05d}",
        order_date=timezone.localdate(),
        expected_delivery=timezone.localdate() + timedelta(days=14),
    )
    line = PurchaseOrderLine.objects.create(
        order=order,
        product=product,
        unit=product.units.get(code=unit_code),
        quantity_ordered=Decimal(quantity),
        unit_price=Decimal(price),
    )
    return order, line


def test_a_line_records_what_the_supplier_trades_in(org, paracetamol):
    """Ten cartons stays ten cartons on the document."""
    _, line = order_for(org, paracetamol, unit_code="CARTON", quantity=10, price="240000")
    assert line.quantity_ordered == Decimal("10.000")
    assert line.unit.code == "CARTON"


def test_ten_cartons_is_twenty_four_thousand_tablets(org, paracetamol):
    """The conversion the shelf depends on."""
    _, line = order_for(org, paracetamol, unit_code="CARTON", quantity=10, price="240000")
    assert line.quantity_ordered_base == Decimal("24000.000")
    assert line.quantity_base == Decimal("24000.000"), "kept in step on save"


def test_the_cost_that_reaches_the_shelf_is_per_tablet(org, paracetamol):
    """A carton at 240,000 is 100 per tablet.

    Carrying the carton price onto the shelf would overstate inventory by the
    pack factor and make every margin derived from it wrong.
    """
    _, line = order_for(org, paracetamol, unit_code="CARTON", quantity=10, price="240000")
    assert line.base_unit_cost == Decimal("100.00")


def test_buying_in_boxes_costs_per_tablet_too(org, paracetamol):
    _, line = order_for(org, paracetamol, unit_code="PACK", quantity=5, price="12000")
    assert line.quantity_ordered_base == Decimal("500.000")
    assert line.base_unit_cost == Decimal("120.00")


def test_buying_singles_is_unchanged(org, paracetamol):
    """A pharmacy that buys loose tablets behaves exactly as before."""
    _, line = order_for(org, paracetamol, unit_code="TABLET", quantity=500, price="120")
    assert line.quantity_ordered_base == Decimal("500.000")
    assert line.base_unit_cost == Decimal("120.00")


def test_a_line_with_no_unit_is_read_as_singles(org, paracetamol):
    """Lines written before units existed had no other unit to be in."""
    supplier = Supplier.objects.create(name="Legacy Supplier")
    order = PurchaseOrder.objects.create(
        organization=org,
        supplier=supplier,
        po_number="PO-LEGACY",
        order_date=timezone.localdate(),
    )
    line = PurchaseOrderLine.objects.create(
        order=order, product=paracetamol, quantity_ordered=Decimal("50"), unit_price=Decimal("120")
    )
    assert line.pack_factor == Decimal(1)
    assert line.quantity_ordered_base == Decimal("50.000")
    assert line.base_unit_cost == Decimal("120.00")


def test_changing_the_unit_restates_the_base_amount(org, paracetamol):
    """The denormalised figure cannot be allowed to drift from the unit."""
    _, line = order_for(org, paracetamol, unit_code="PACK", quantity=3, price="12000")
    assert line.quantity_base == Decimal("300.000")

    line.unit = paracetamol.units.get(code="CARTON")
    line.save()
    line.refresh_from_db()
    assert line.quantity_base == Decimal("7200.000")
