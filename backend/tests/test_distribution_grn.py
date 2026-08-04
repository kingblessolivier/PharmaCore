"""Lean reception: order → approve (ships) → receive lands the stock at retail.

Receiving is one click — no per-item counting. Stock accumulates onto any
existing batch (no duplicate), and the product is auto-listed in the retail
catalog with all its characteristics.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, StockOrder
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement
from rest_framework.test import APIClient

BASE = "/api/distribution"


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Central Depot", type="DEPOT")


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Branch Pharmacy", type="RETAIL")


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


@pytest.fixture
def sysadmin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


def _in_transit_order(depot, retail, product, admin, order_qty=40, batch_qty=100) -> StockOrder:
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number="AMX-2311",
        expiry_date=date.today() + timedelta(days=120),
        quantity_available=batch_qty,
    )
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(
        order=order, product=product, quantity_ordered=order_qty, price_per_unit=10
    )
    _auth(admin).post(f"{BASE}/orders/{order.pk}/approve/")  # approve = ship
    order.refresh_from_db()
    assert order.status == StockOrder.Status.IN_TRANSIT
    return order


@pytest.mark.django_db
def test_receive_lands_stock_and_auto_lists(sysadmin, depot, retail, product) -> None:
    order = _in_transit_order(depot, retail, product, sysadmin, order_qty=40)
    resp = _auth(sysadmin).post(f"{BASE}/orders/{order.pk}/receive/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DELIVERED"

    # Retail now holds the full 40 as a TRANSFER_IN, on the same batch/expiry.
    rbatch = InventoryBatch.objects.get(organization=retail, batch_number="AMX-2311")
    assert rbatch.quantity_available == 40
    assert StockMovement.objects.filter(
        organization=retail, movement_type=StockMovement.Type.TRANSFER_IN
    ).exists()
    # Auto-listed in the retail catalog (no re-adding), price left blank.
    listing = PharmacyProduct.objects.get(organization=retail, product=product)
    assert listing.retail_price is None
    assert order.items.first().quantity_received == 40
    # Recall traceability: the retail lot knows which depot it came from.
    assert rbatch.source_org_id == depot.pk


@pytest.mark.django_db
def test_receive_accumulates_onto_existing_stock(sysadmin, depot, retail, product) -> None:
    # Retail already has 2 of this exact batch on hand.
    InventoryBatch.objects.create(
        organization=retail,
        product=product,
        batch_number="AMX-2311",
        expiry_date=date.today() + timedelta(days=120),
        quantity_available=2,
    )
    order = _in_transit_order(depot, retail, product, sysadmin, order_qty=12)
    _auth(sysadmin).post(f"{BASE}/orders/{order.pk}/receive/")
    # 2 existing + 12 received = 14 on one batch — never a duplicate.
    batches = InventoryBatch.objects.filter(
        organization=retail, product=product, batch_number="AMX-2311"
    )
    assert batches.count() == 1
    assert batches.first().quantity_available == 14


@pytest.mark.django_db
def test_in_transit_ledger_holds_then_clears(sysadmin, depot, retail, product) -> None:
    from apps.distribution.models import InTransitStock

    order = _in_transit_order(depot, retail, product, sysadmin, order_qty=40)
    # After dispatch: the 40 units are held in the in-transit ledger (counted, not lost).
    it = InTransitStock.objects.filter(order=order)
    assert it.count() == 1
    assert sum(r.quantity for r in it) == 40
    assert it.first().source_org_id == depot.pk
    assert it.first().destination_org_id == retail.pk
    dbatch = InventoryBatch.objects.get(organization=depot, batch_number="AMX-2311")
    # Conservation: depot has 60 left, 40 in transit, 0 at retail = 100 total.
    assert dbatch.quantity_available == 60

    _auth(sysadmin).post(f"{BASE}/orders/{order.pk}/receive/")
    # After receipt: ledger cleared, retail holds the 40.
    assert InTransitStock.objects.filter(order=order).count() == 0
    assert (
        InventoryBatch.objects.get(organization=retail, batch_number="AMX-2311").quantity_available
        == 40
    )


@pytest.mark.django_db
def test_cannot_receive_before_approval(sysadmin, depot, retail, product) -> None:
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(order=order, product=product, quantity_ordered=5, price_per_unit=1)
    resp = _auth(sysadmin).post(f"{BASE}/orders/{order.pk}/receive/")
    assert resp.status_code == 400
