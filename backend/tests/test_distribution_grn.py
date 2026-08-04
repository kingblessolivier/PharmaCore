"""GRN reception: order → dispatch → receive → finalize creates retail stock."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import GoodsReceivedNote, OrderItem, StockOrder
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, StockMovement
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


def _dispatched_order(depot, retail, product, admin) -> StockOrder:
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number="AMX-2311",
        expiry_date=date.today() + timedelta(days=120),
        quantity_available=100,
    )
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(order=order, product=product, quantity_ordered=40, price_per_unit=10)
    c = _auth(admin)
    c.post(f"{BASE}/orders/{order.pk}/approve/")
    c.post(f"{BASE}/orders/{order.pk}/pick/")
    c.post(f"{BASE}/orders/{order.pk}/dispatch/", {"driver_name": "J"}, format="json")
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_receive_and_finalize_creates_retail_stock(sysadmin, depot, retail, product) -> None:
    order = _dispatched_order(depot, retail, product, sysadmin)
    assert order.status == StockOrder.Status.IN_TRANSIT
    client = _auth(sysadmin)

    # Open GRN — pre-filled from the shipment manifest (batch AMX-2311 × 40).
    opened = client.post(f"{BASE}/orders/{order.pk}/receive/")
    assert opened.status_code == 201
    grn_id = opened.json()["id"]
    lines = opened.json()["lines"]
    assert lines[0]["batch_number"] == "AMX-2311"
    assert lines[0]["quantity_expected"] == 40

    # Finalize with a shortfall: only 35 received, 2 damaged.
    resp = client.post(
        f"{BASE}/grns/{grn_id}/finalize/",
        {"lines": [{"id": lines[0]["id"], "quantity_received": 35, "quantity_damaged": 2}]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FINALIZED"
    assert resp.json()["has_discrepancy"] is True

    # Retail now holds the good stock (35 received − 2 damaged = 33) as a TRANSFER_IN.
    rbatch = InventoryBatch.objects.get(organization=retail, batch_number="AMX-2311")
    assert rbatch.quantity_available == 33
    assert StockMovement.objects.filter(
        organization=retail, movement_type=StockMovement.Type.TRANSFER_IN
    ).exists()

    order.refresh_from_db()
    assert order.status == StockOrder.Status.PARTIALLY_RECEIVED  # 35 < 40 shipped
    assert order.items.first().quantity_received == 35


@pytest.mark.django_db
def test_cannot_receive_before_dispatch(sysadmin, depot, retail, product) -> None:
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.PENDING)
    OrderItem.objects.create(order=order, product=product, quantity_ordered=5, price_per_unit=1)
    resp = _auth(sysadmin).post(f"{BASE}/orders/{order.pk}/receive/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_full_receipt_marks_delivered(sysadmin, depot, retail, product) -> None:
    order = _dispatched_order(depot, retail, product, sysadmin)
    client = _auth(sysadmin)
    opened = client.post(f"{BASE}/orders/{order.pk}/receive/").json()
    client.post(f"{BASE}/grns/{opened['id']}/finalize/", {"lines": []}, format="json")
    order.refresh_from_db()
    assert order.status == StockOrder.Status.DELIVERED  # defaults received = expected (40)
    assert GoodsReceivedNote.objects.get(pk=opened["id"]).has_discrepancy is False
