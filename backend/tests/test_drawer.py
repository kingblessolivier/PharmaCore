"""Cash-drawer / till sessions: open with a float, ring up sales, cash up (over/short)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def pharmacy(db: None) -> Organization:
    return Organization.objects.create(name="City Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


@pytest.fixture
def listing(pharmacy: Organization, product: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=pharmacy, product=product, retail_price="1000.00"
    )


@pytest.fixture
def cashier(pharmacy: Organization) -> User:
    u = User.objects.create_user(username="till1", password="x", organization=pharmacy)
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


def _open(client: APIClient, pharmacy: Organization, float_amount: str) -> dict:
    resp = client.post(
        "/api/retail/drawer-sessions/",
        {"organization": pharmacy.pk, "opening_float": float_amount},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


def _ring_cash_sale(
    client: APIClient, pharmacy: Organization, product: Product, qty: int, pay: str
) -> None:
    resp = client.post(
        "/api/retail/sales/",
        {
            "organization": pharmacy.pk,
            "items": [{"product": product.pk, "quantity": qty}],
            "payments": [{"method": "CASH", "amount": pay}],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content


@pytest.mark.django_db
def test_open_drawer(cashier: User, pharmacy: Organization) -> None:
    body = _open(_auth(cashier), pharmacy, "10000")
    assert body["status"] == "OPEN"
    assert body["opening_float"] == "10000.00"
    assert AuditLog.objects.filter(action="DRAWER_OPEN").exists()


@pytest.mark.django_db
def test_cannot_open_two_drawers(cashier: User, pharmacy: Organization) -> None:
    client = _auth(cashier)
    _open(client, pharmacy, "10000")
    resp = client.post(
        "/api/retail/drawer-sessions/",
        {"organization": pharmacy.pk, "opening_float": "5000"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_sale_links_to_open_drawer_and_report_math(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    client = _auth(cashier)
    session = _open(client, pharmacy, "10000")
    InventoryBatch.objects.create(
        organization=pharmacy,
        product=product,
        batch_number="B1",
        expiry_date=date.today() + timedelta(days=200),
        quantity_available=50,
    )
    # 3 × 1000 = 3000 total; tender 5000 cash → change 2000.
    _ring_cash_sale(client, pharmacy, product, 3, "5000")

    resp = client.get(f"/api/retail/drawer-sessions/{session['id']}/report/")
    assert resp.status_code == 200, resp.content
    report = resp.json()["report"]
    assert report["sales_count"] == 1
    assert report["cash_payments"] == "5000.00"
    assert report["change_given"] == "2000.00"
    # expected = 10000 float + 5000 cash − 2000 change = 13000 (net 3000 from the sale)
    assert report["expected_cash"] == "13000.00"


@pytest.mark.django_db
def test_current_returns_open_drawer(cashier: User, pharmacy: Organization) -> None:
    client = _auth(cashier)
    _open(client, pharmacy, "8000")
    resp = client.get(f"/api/retail/drawer-sessions/current/?organization={pharmacy.pk}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "OPEN"
    assert "report" in resp.json()


@pytest.mark.django_db
def test_current_204_when_no_open_drawer(cashier: User, pharmacy: Organization) -> None:
    resp = _auth(cashier).get(f"/api/retail/drawer-sessions/current/?organization={pharmacy.pk}")
    assert resp.status_code == 204


@pytest.mark.django_db
def test_close_computes_over_short(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    client = _auth(cashier)
    session = _open(client, pharmacy, "10000")
    InventoryBatch.objects.create(
        organization=pharmacy,
        product=product,
        batch_number="B1",
        expiry_date=date.today() + timedelta(days=200),
        quantity_available=50,
    )
    _ring_cash_sale(client, pharmacy, product, 3, "5000")  # net +3000 → expected 13000

    # Cashier counts 12,500 → short by 500.
    resp = client.post(
        f"/api/retail/drawer-sessions/{session['id']}/close/",
        {"counted_cash": "12500", "notes": "one 500 note missing"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "CLOSED"
    assert body["expected_cash"] == "13000.00"
    assert body["counted_cash"] == "12500.00"
    assert body["over_short"] == "-500.00"
    assert AuditLog.objects.filter(action="DRAWER_CLOSE").exists()

    # A closed drawer cannot be closed again.
    again = client.post(
        f"/api/retail/drawer-sessions/{session['id']}/close/",
        {"counted_cash": "13000"},
        format="json",
    )
    assert again.status_code == 400


@pytest.mark.django_db
def test_close_requires_counted_cash(cashier: User, pharmacy: Organization) -> None:
    client = _auth(cashier)
    session = _open(client, pharmacy, "10000")
    resp = client.post(f"/api/retail/drawer-sessions/{session['id']}/close/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_other_cashier_cannot_close(cashier: User, pharmacy: Organization) -> None:
    client = _auth(cashier)
    session = _open(client, pharmacy, "10000")
    other = User.objects.create_user(username="till2", password="x", organization=pharmacy)
    other.roles.add(Role.objects.get(code="CASHIER"))
    resp = _auth(other).post(
        f"/api/retail/drawer-sessions/{session['id']}/close/",
        {"counted_cash": "10000"},
        format="json",
    )
    assert resp.status_code == 403
