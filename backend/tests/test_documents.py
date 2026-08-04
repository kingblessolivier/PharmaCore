"""Document engine: generation, numbering, hashing, QR verification, and wiring
into the distribution flow (PO, delivery note, GRN, tax invoice)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, StockOrder
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch
from rest_framework.test import APIClient

BASE = "/api/distribution"


@pytest.fixture(autouse=True)
def _media(tmp_path, settings) -> None:
    settings.MEDIA_ROOT = tmp_path


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Central Depot", type="DEPOT", tin="100200300")


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Branch Pharmacy", type="RETAIL")


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg", tax_class="B")


@pytest.fixture
def sysadmin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.mark.django_db
def test_generate_produces_numbered_hashed_pdf(depot: Organization) -> None:
    doc = generate_document(
        organization=depot,
        doc_type=DocType.PURCHASE_ORDER,
        context={"buyer_name": "A", "seller_name": "B", "lines": [], "total": 0},
        reference_type="test",
        reference_id="1",
    )
    assert doc.doc_number.startswith("PO-")
    assert len(doc.content_hash) == 64
    assert doc.file.read().startswith(b"%PDF")


@pytest.mark.django_db
def test_public_verify_confirms_authenticity(depot: Organization) -> None:
    doc = generate_document(
        organization=depot,
        doc_type=DocType.DELIVERY_NOTE,
        context={"from_name": "A", "to_name": "B", "driver": "", "vehicle": "", "lines": []},
    )
    resp = APIClient().get(f"/api/documents/verify/{doc.qr_token}/")
    assert resp.status_code == 200
    assert resp.json()["authentic"] is True
    assert resp.json()["doc_number"] == doc.doc_number


@pytest.mark.django_db
def test_full_flow_generates_all_documents(sysadmin, depot, retail, product) -> None:
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number="AMX-1",
        expiry_date=date.today() + timedelta(days=90),
        quantity_available=50,
    )
    order = StockOrder.objects.create(depot=depot, retail=retail, status=StockOrder.Status.DRAFT)
    OrderItem.objects.create(order=order, product=product, quantity_ordered=20, price_per_unit=10)
    c = _auth(sysadmin)
    c.post(f"{BASE}/orders/{order.pk}/submit/")  # PO
    c.post(f"{BASE}/orders/{order.pk}/approve/")  # approve + ship → Delivery note
    c.post(f"{BASE}/orders/{order.pk}/receive/")  # land stock → GRN + Tax invoice

    types = set(Document.objects.values_list("doc_type", flat=True))
    assert {"PURCHASE_ORDER", "DELIVERY_NOTE", "GRN", "TAX_INVOICE"} <= types

    # The document vault lists them, and download returns a PDF.
    listed = c.get("/api/documents/").json()
    assert listed["count"] >= 4
    doc_id = listed["results"][0]["id"]
    dl = c.get(f"/api/documents/{doc_id}/download/")
    assert dl.status_code == 200
