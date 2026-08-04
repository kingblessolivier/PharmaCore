"""Depot approval + FEFO allocation (reservation) for purchase orders."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, Reservation, StockOrder
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch
from rest_framework.test import APIClient


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


def _batch(org: Organization, product: Product, num: str, days: int, qty: int) -> InventoryBatch:
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=num,
        expiry_date=date.today() + timedelta(days=days),
        quantity_available=qty,
    )


def _pending_order(
    depot: Organization, retail: Organization, product: Product, qty: int
) -> StockOrder:
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(order=order, product=product, quantity_ordered=qty, price_per_unit=10)
    return order


@pytest.mark.django_db
def test_approve_reserves_fefo(depot_admin, depot, retail, product) -> None:
    b1 = _batch(depot, product, "B1", 30, 60)  # expires sooner
    b2 = _batch(depot, product, "B2", 300, 80)  # expires later
    order = _pending_order(depot, retail, product, 100)

    resp = _auth(depot_admin).post(f"/api/distribution/orders/{order.pk}/approve/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    b1.refresh_from_db()
    b2.refresh_from_db()
    # FEFO: soonest-expiring batch fully reserved first, then the next.
    assert b1.quantity_reserved == 60
    assert b2.quantity_reserved == 40
    assert order.items.first().quantity_approved == 100
    assert Reservation.objects.filter(order=order).count() == 2


@pytest.mark.django_db
def test_partial_reservation_when_short(depot_admin, depot, retail, product) -> None:
    _batch(depot, product, "B1", 30, 40)
    order = _pending_order(depot, retail, product, 100)
    resp = _auth(depot_admin).post(f"/api/distribution/orders/{order.pk}/approve/")
    assert resp.status_code == 200
    # Approved fully, but only 40 could be reserved.
    assert order.items.first().quantity_approved == 100
    assert sum(r.quantity for r in Reservation.objects.filter(order=order)) == 40


@pytest.mark.django_db
def test_non_depot_user_cannot_approve(retail, depot, product) -> None:
    other = User.objects.create_user(username="clerk", password="x", organization=retail)
    order = _pending_order(depot, retail, product, 10)
    resp = _auth(other).post(f"/api/distribution/orders/{order.pk}/approve/")
    assert resp.status_code in (403, 404)  # not visible / not permitted
    order.refresh_from_db()
    assert order.status == StockOrder.Status.PENDING


@pytest.mark.django_db
def test_cancel_releases_reservations(depot_admin, depot, retail, product) -> None:
    b1 = _batch(depot, product, "B1", 30, 100)
    order = _pending_order(depot, retail, product, 50)
    _auth(depot_admin).post(f"/api/distribution/orders/{order.pk}/approve/")
    b1.refresh_from_db()
    assert b1.quantity_reserved == 50

    resp = _auth(depot_admin).post(f"/api/distribution/orders/{order.pk}/cancel/")
    assert resp.status_code == 200
    b1.refresh_from_db()
    assert b1.quantity_reserved == 0
    assert Reservation.objects.filter(order=order).count() == 0
