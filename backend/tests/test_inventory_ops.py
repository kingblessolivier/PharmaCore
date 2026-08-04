"""Inventory ops: adjustments, wastage (never-negative), expiry filter."""

from __future__ import annotations

import datetime

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import StockMovement
from apps.inventory.services import receive_intake
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
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


def _batch(retail: Organization, product: Product, qty: int = 100, exp: str = "2028-01-01"):
    return receive_intake(
        organization=retail,
        product=product,
        batch_number="B1",
        expiry_date=datetime.date.fromisoformat(exp),
        quantity=qty,
    )


@pytest.mark.django_db
def test_adjust_updates_qty_and_logs_delta(
    admin: User, retail: Organization, product: Product
) -> None:
    batch = _batch(retail, product, 100)
    resp = _auth(admin).post(
        f"/api/inventory/batches/{batch.pk}/adjust/",
        {"counted_quantity": 95, "reason": "count"},
        format="json",
    )
    assert resp.status_code == 200
    batch.refresh_from_db()
    assert batch.quantity_available == 95
    mv = StockMovement.objects.get(batch=batch, movement_type="ADJUSTMENT")
    assert mv.quantity_delta == -5
    assert AuditLog.objects.filter(action="ADJUSTMENT").exists()


@pytest.mark.django_db
def test_waste_reduces_qty(admin: User, retail: Organization, product: Product) -> None:
    batch = _batch(retail, product, 100)
    resp = _auth(admin).post(
        f"/api/inventory/batches/{batch.pk}/waste/",
        {"quantity": 10, "reason": "expired"},
        format="json",
    )
    assert resp.status_code == 200
    batch.refresh_from_db()
    assert batch.quantity_available == 90
    assert StockMovement.objects.filter(
        batch=batch, movement_type="WASTAGE", quantity_delta=-10
    ).exists()


@pytest.mark.django_db
def test_cannot_waste_more_than_on_hand(
    admin: User, retail: Organization, product: Product
) -> None:
    batch = _batch(retail, product, 5)
    resp = _auth(admin).post(
        f"/api/inventory/batches/{batch.pk}/waste/", {"quantity": 10}, format="json"
    )
    assert resp.status_code == 400
    batch.refresh_from_db()
    assert batch.quantity_available == 5  # unchanged


@pytest.mark.django_db
def test_non_admin_cannot_adjust(retail: Organization, product: Product) -> None:
    batch = _batch(retail, product, 100)
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    resp = _auth(plain).post(
        f"/api/inventory/batches/{batch.pk}/adjust/", {"counted_quantity": 1}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_expiring_within_filter(admin: User, retail: Organization, product: Product) -> None:
    receive_intake(
        organization=retail,
        product=product,
        batch_number="SOON",
        expiry_date=datetime.date.today() + datetime.timedelta(days=30),
        quantity=10,
    )
    receive_intake(
        organization=retail,
        product=product,
        batch_number="FAR",
        expiry_date=datetime.date.today() + datetime.timedelta(days=400),
        quantity=10,
    )
    resp = _auth(admin).get(f"/api/inventory/batches/?organization={retail.pk}&expiring_within=90")
    nums = {b["batch_number"] for b in resp.json()["results"]}
    assert nums == {"SOON"}
