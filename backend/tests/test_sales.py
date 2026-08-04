"""Retail POS sales: ring up → FEFO deduct → pay → receipt, plus void reversal.

Prices are pulled from the pharmacy's own listing (never the client); stock is
consumed soonest-expiring-first; totals are VAT-inclusive (tax class B = 18%).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.documents.models import Document
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement
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
    # Tax class B → 18% VAT (inclusive).
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


@pytest.fixture
def listing(pharmacy: Organization, product: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=pharmacy, product=product, retail_price="1000.00"
    )


def _batch(pharmacy: Organization, product: Product, qty: int, expiry: date) -> InventoryBatch:
    return InventoryBatch.objects.create(
        organization=pharmacy,
        product=product,
        batch_number=f"B{expiry.isoformat()}",
        expiry_date=expiry,
        quantity_available=qty,
    )


@pytest.fixture
def cashier(pharmacy: Organization) -> User:
    u = User.objects.create_user(username="till1", password="x", organization=pharmacy)
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


def _sale_payload(pharmacy: Organization, product: Product, qty: int, pay: str | None) -> dict:
    body: dict = {"organization": pharmacy.pk, "items": [{"product": product.pk, "quantity": qty}]}
    if pay is not None:
        body["payments"] = [{"method": "CASH", "amount": pay}]
    return body


@pytest.mark.django_db
def test_sale_pulls_price_and_completes(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    _batch(pharmacy, product, 50, date.today() + timedelta(days=200))
    resp = _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 3, "5000"), format="json"
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["sale_number"].startswith("SALE-")
    assert body["status"] == "COMPLETED"
    # 3 × 1000 (VAT-inclusive)
    assert body["total"] == "3000.00"
    # VAT portion of a B-class inclusive price: 3000 × 18/118 = 457.63
    assert body["tax_total"] == "457.63"
    assert body["subtotal"] == "2542.37"
    assert body["change_due"] == "2000.00"
    assert body["items"][0]["unit_price"] == "1000.00"


@pytest.mark.django_db
def test_completion_deducts_stock_fefo(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    soon = _batch(pharmacy, product, 5, date.today() + timedelta(days=30))
    later = _batch(pharmacy, product, 50, date.today() + timedelta(days=300))
    resp = _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 8, "8000"), format="json"
    )
    assert resp.status_code == 201, resp.content
    soon.refresh_from_db()
    later.refresh_from_db()
    # FEFO: the 5 soonest-expiring go first, then 3 from the later batch.
    assert soon.quantity_available == 0
    assert later.quantity_available == 47
    moves = StockMovement.objects.filter(product=product, movement_type="SALE")
    assert (
        sorted(m.quantity_delta for m in moves) == [-5, -3]
        or sorted(m.quantity_delta for m in moves) == [-5, -3][::-1]
    )


@pytest.mark.django_db
def test_receipt_generated(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    _batch(pharmacy, product, 10, date.today() + timedelta(days=200))
    _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 1, "1000"), format="json"
    )
    assert Document.objects.filter(doc_type="RECEIPT", organization=pharmacy).exists()
    assert AuditLog.objects.filter(action="SALE_COMPLETE", entity_type="sale").exists()


@pytest.mark.django_db
def test_oversell_rejected_no_stock_change(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    batch = _batch(pharmacy, product, 2, date.today() + timedelta(days=100))
    resp = _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 5, "5000"), format="json"
    )
    assert resp.status_code == 400
    assert "in stock" in str(resp.content)
    batch.refresh_from_db()
    assert batch.quantity_available == 2  # untouched (atomic rollback)
    assert not StockMovement.objects.filter(movement_type="SALE").exists()


@pytest.mark.django_db
def test_unlisted_product_rejected(cashier: User, pharmacy: Organization, product: Product) -> None:
    # No PharmacyProduct listing → no retail price → 400.
    _batch(pharmacy, product, 10, date.today() + timedelta(days=100))
    resp = _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 1, "1000"), format="json"
    )
    assert resp.status_code == 400
    assert "retail price" in str(resp.content)


@pytest.mark.django_db
def test_short_payment_rejected(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    _batch(pharmacy, product, 10, date.today() + timedelta(days=100))
    resp = _auth(cashier).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 3, "1000"), format="json"
    )
    assert resp.status_code == 400
    assert "does not cover" in str(resp.content)


@pytest.mark.django_db
def test_hold_then_complete(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    _batch(pharmacy, product, 10, date.today() + timedelta(days=100))
    client = _auth(cashier)
    held = client.post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 2, None), format="json"
    ).json()
    assert held["status"] == "OPEN"
    done = client.post(
        f"/api/retail/sales/{held['id']}/complete/",
        {"payments": [{"method": "CASH", "amount": "2000"}]},
        format="json",
    )
    assert done.status_code == 200
    assert done.json()["status"] == "COMPLETED"


@pytest.mark.django_db
def test_void_reverses_stock(
    cashier: User, pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    batch = _batch(pharmacy, product, 10, date.today() + timedelta(days=100))
    client = _auth(cashier)
    sale_id = client.post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 4, "4000"), format="json"
    ).json()["id"]
    batch.refresh_from_db()
    assert batch.quantity_available == 6
    voided = client.post(
        f"/api/retail/sales/{sale_id}/void/", {"reason": "customer changed mind"}, format="json"
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "VOIDED"
    batch.refresh_from_db()
    assert batch.quantity_available == 10  # returned
    assert StockMovement.objects.filter(movement_type="RETURN", quantity_delta=4).exists()


@pytest.mark.django_db
def test_cannot_sell_for_other_pharmacy(
    pharmacy: Organization, product: Product, listing: PharmacyProduct
) -> None:
    other_org = Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)
    outsider = User.objects.create_user(username="x", password="x", organization=other_org)
    outsider.roles.add(Role.objects.get(code="CASHIER"))
    _batch(pharmacy, product, 10, date.today() + timedelta(days=100))
    resp = _auth(outsider).post(
        "/api/retail/sales/", _sale_payload(pharmacy, product, 1, "1000"), format="json"
    )
    assert resp.status_code == 403
