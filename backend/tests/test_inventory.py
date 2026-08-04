"""Inventory core: intake creates batch + immutable movement, FEFO, never-negative."""

from __future__ import annotations

import datetime

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import InventoryBatch, StockMovement
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


@pytest.mark.django_db
def test_intake_creates_batch_and_movement(
    admin: User, retail: Organization, product: Product
) -> None:
    resp = _auth(admin).post(
        "/api/inventory/intake",
        {
            "organization": retail.pk,
            "product": product.pk,
            "batch_number": "AMX-2311",
            "expiry_date": "2027-02-01",
            "quantity": 240,
            "wholesale_cost": "800.00",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    batch = InventoryBatch.objects.get(organization=retail, batch_number="AMX-2311")
    assert batch.quantity_available == 240
    mv = StockMovement.objects.get(batch=batch)
    assert mv.movement_type == "INTAKE" and mv.quantity_delta == 240
    assert AuditLog.objects.filter(action="INTAKE", entity_type="inventory_batch").exists()


@pytest.mark.django_db
def test_intake_adds_to_existing_batch(admin: User, retail: Organization, product: Product) -> None:
    client = _auth(admin)
    body = {
        "organization": retail.pk,
        "product": product.pk,
        "batch_number": "B1",
        "expiry_date": "2027-01-01",
        "quantity": 100,
    }
    client.post("/api/inventory/intake", body, format="json")
    client.post("/api/inventory/intake", {**body, "quantity": 50}, format="json")
    batch = InventoryBatch.objects.get(batch_number="B1")
    assert batch.quantity_available == 150
    assert StockMovement.objects.filter(batch=batch).count() == 2


@pytest.mark.django_db
def test_non_admin_cannot_receive_intake(retail: Organization, product: Product) -> None:
    plain = User.objects.create_user(username="p", password="x", organization=retail)
    resp = _auth(plain).post(
        "/api/inventory/intake",
        {
            "organization": retail.pk,
            "product": product.pk,
            "batch_number": "X",
            "expiry_date": "2027-01-01",
            "quantity": 5,
        },
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_batches_listed_fefo(admin: User, retail: Organization, product: Product) -> None:
    receive_intake(
        organization=retail,
        product=product,
        batch_number="LATE",
        expiry_date=datetime.date(2028, 1, 1),
        quantity=10,
    )
    receive_intake(
        organization=retail,
        product=product,
        batch_number="SOON",
        expiry_date=datetime.date(2026, 3, 1),
        quantity=10,
    )
    resp = _auth(admin).get(f"/api/inventory/batches/?organization={retail.pk}")
    order = [b["batch_number"] for b in resp.json()["results"]]
    assert order == ["SOON", "LATE"]  # soonest-expiring first (FEFO)


@pytest.mark.django_db
def test_stock_movement_is_append_only(retail: Organization, product: Product) -> None:
    batch = receive_intake(
        organization=retail,
        product=product,
        batch_number="B",
        expiry_date=datetime.date(2027, 1, 1),
        quantity=10,
    )
    mv = batch.movements.first()
    assert mv is not None
    mv.quantity_delta = 999
    with pytest.raises(ValueError, match="append-only"):
        mv.save()
    with pytest.raises(ValueError, match="append-only"):
        mv.delete()
