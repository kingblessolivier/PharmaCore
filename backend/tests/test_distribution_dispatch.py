"""Picking & dispatch: consume reservations, deduct depot stock via TRANSFER_OUT."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, Reservation, Shipment, StockOrder
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, StockMovement
from rest_framework.test import APIClient

BASE = "/api/distribution/orders"


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
def depot_admin(depot: Organization) -> User:
    u = User.objects.create_user(username="depotadmin", password="x", organization=depot)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


def _approved_order(depot, retail, product, batch_qty, order_qty, admin) -> StockOrder:
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number="B1",
        expiry_date=date.today() + timedelta(days=90),
        quantity_available=batch_qty,
    )
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(
        order=order, product=product, quantity_ordered=order_qty, price_per_unit=10
    )
    _auth(admin).post(f"{BASE}/{order.pk}/approve/")
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_pick_then_dispatch_moves_stock(depot_admin, depot, retail, product) -> None:
    order = _approved_order(depot, retail, product, batch_qty=100, order_qty=40, admin=depot_admin)
    client = _auth(depot_admin)

    assert client.post(f"{BASE}/{order.pk}/pick/").status_code == 200
    order.refresh_from_db()
    assert order.status == StockOrder.Status.PICKING

    resp = client.post(
        f"{BASE}/{order.pk}/dispatch/",
        {"driver_name": "Jean", "vehicle_registration": "RAD 123 A"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_TRANSIT"

    batch = InventoryBatch.objects.get(organization=depot, batch_number="B1")
    assert batch.quantity_available == 60  # 100 - 40 dispatched
    assert batch.quantity_reserved == 0  # reservation consumed
    assert Reservation.objects.filter(order=order).count() == 0
    assert order.items.first().quantity_shipped == 40
    assert Shipment.objects.filter(order=order, driver_name="Jean").exists()
    mv = StockMovement.objects.get(reference_type="shipment", reference_id=str(order.pk))
    assert mv.movement_type == StockMovement.Type.TRANSFER_OUT
    assert mv.quantity_delta == -40


@pytest.mark.django_db
def test_cannot_dispatch_before_picking(depot_admin, depot, retail, product) -> None:
    order = _approved_order(depot, retail, product, batch_qty=100, order_qty=10, admin=depot_admin)
    resp = _auth(depot_admin).post(f"{BASE}/{order.pk}/dispatch/", {}, format="json")
    assert resp.status_code == 400  # must be PICKING first


@pytest.mark.django_db
def test_non_depot_cannot_dispatch(depot_admin, depot, retail, product) -> None:
    order = _approved_order(depot, retail, product, batch_qty=100, order_qty=10, admin=depot_admin)
    _auth(depot_admin).post(f"{BASE}/{order.pk}/pick/")
    outsider = User.objects.create_user(username="clerk", password="x", organization=retail)
    resp = _auth(outsider).post(f"{BASE}/{order.pk}/dispatch/", {}, format="json")
    assert resp.status_code in (403, 404)
