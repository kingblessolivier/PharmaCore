"""Operational dashboard summary — scoped counts a manager sees on the home screen."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, StockOrder
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_dashboard_summarises_the_users_org() -> None:
    depot = Organization.objects.create(name="Depot", type=Organization.OrgType.DEPOT)
    retail = Organization.objects.create(name="Shop", type=Organization.OrgType.RETAIL)
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")

    manager = User.objects.create_user(username="mgr", password="x", organization=retail)
    manager.roles.add(Role.objects.get(code="ORG_ADMIN"))

    # Low stock: min 20, only 5 on hand (non-expired).
    PharmacyProduct.objects.create(
        organization=retail, product=product, retail_price="1000", min_stock_level=20
    )
    InventoryBatch.objects.create(
        organization=retail,
        product=product,
        batch_number="B1",
        expiry_date=date.today() + timedelta(days=200),
        quantity_available=5,
    )
    # An order awaiting this pharmacy to receive, with money owed.
    order = StockOrder.objects.create(
        depot=depot, retail=retail, status=StockOrder.Status.IN_TRANSIT
    )
    OrderItem.objects.create(order=order, product=product, quantity_ordered=10, price_per_unit=100)

    resp = _auth(manager).get("/api/dashboard/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["low_stock"]["count"] == 1
    assert body["low_stock"]["items"][0]["on_hand"] == 5
    assert body["awaiting_receipt"] == 1
    # Retail owes the wholesaler 10 × 100 = 1000 (unpaid).
    assert body["payable_due"] == 1000.0
    assert body["sales_today"]["count"] == 0


@pytest.mark.django_db
def test_aging_report_splits_receivable_and_payable() -> None:
    depot = Organization.objects.create(name="Depot", type=Organization.OrgType.DEPOT)
    retail = Organization.objects.create(name="Shop", type=Organization.OrgType.RETAIL)
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    admin = User.objects.create_user(username="root2", password="x")
    admin.roles.add(Role.objects.get(code="SYS_ADMIN"))

    order = StockOrder.objects.create(
        depot=depot, retail=retail, status=StockOrder.Status.DELIVERED
    )
    OrderItem.objects.create(order=order, product=product, quantity_ordered=10, price_per_unit=100)

    body = _auth(admin).get("/api/distribution/aging/").json()
    # Admin sees all: this order is both a receivable (for depot) and payable (for retail).
    assert body["receivables"]["total"] == 1000.0
    assert body["payables"]["total"] == 1000.0
    assert body["receivables"]["by_partner"][0]["partner"] == "Shop"
    assert body["payables"]["by_partner"][0]["partner"] == "Depot"
