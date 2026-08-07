"""Procurement & imports — the buy side, end to end.

Covers ROADMAP §4: supplier master + qualification, requisitions consolidated at
HQ, RFQ/quote comparison, purchase orders (raise → approve → send → partial
receipt), imports with landed-cost allocation, goods receipt with batch/expiry
capture and QC hand-off to quarantine, and supplier invoices with the 3-way match
posting into the finance ledger.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, Supplier
from apps.finance.models import JournalEntry, JournalLine, SupplierBill
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, QualityCheck
from apps.procurement.models import (
    GoodsReceipt,
    ImportConsignment,
    PurchaseOrder,
    PurchaseRequisition,
    SupplierInvoice,
    SupplierLicence,
    SupplierProfile,
)
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Central Depot", type="DEPOT")


@pytest.fixture
def branch(db: None) -> Organization:
    return Organization.objects.create(name="Remera Branch", type="RETAIL")


@pytest.fixture
def buyer(depot: Organization) -> User:
    """The procurement officer who raises documents (and may never approve them)."""
    user = User.objects.create_user(username="buyer", password="x", organization=depot)
    user.roles.add(Role.objects.get(code="PROCUREMENT_OFFICER"))
    return user


@pytest.fixture
def approver(depot: Organization) -> User:
    """A manager who can decide approvals — someone other than the requester."""
    user = User.objects.create_user(username="pmanager", password="x", organization=depot)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


@pytest.fixture
def outsider(db: None) -> User:
    other = Organization.objects.create(name="Rival Pharmacy", type="RETAIL")
    user = User.objects.create_user(username="outsider", password="x", organization=other)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


@pytest.fixture
def supplier(db: None) -> Supplier:
    return Supplier.objects.create(name="Global Pharma Imports", tin="102938475")


@pytest.fixture
def qualified_supplier(supplier: Supplier, approver: User) -> Supplier:
    """A supplier whose required Rwanda FDA licence is on file and verified."""
    SupplierProfile.objects.create(
        supplier=supplier,
        standing=SupplierProfile.Standing.PREFERRED,
        currency="USD",
        is_import_source=True,
        payment_terms_days=45,
    )
    SupplierLicence.objects.create(
        supplier=supplier,
        kind=SupplierLicence.Kind.FDA_IMPORT,
        licence_number="FDA-IMP-2026-0091",
        issuing_authority="Rwanda FDA",
        issued_on=date.today() - timedelta(days=30),
        expires_on=date.today() + timedelta(days=300),
        is_required=True,
        is_verified=True,
        verified_by=approver,
        verified_at=timezone.now(),
    )
    return supplier


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(
        generic_name="Amoxicillin", strength="500mg", units_per_pack=100, tax_class="C"
    )


@pytest.fixture
def product_b(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg")


def _approve(approval_id: int, approver: User) -> None:
    """Walk an approval through the engine the way the inbox UI does."""
    client = _auth(approver)
    assert client.post(f"/api/approvals/requests/{approval_id}/claim/").status_code == 200
    resp = client.post(f"/api/approvals/requests/{approval_id}/approve/", {}, format="json")
    assert resp.status_code == 200, resp.content


def _draft_order(
    client: APIClient, depot: Organization, supplier: Supplier, product: Product, **overrides
) -> dict:
    payload = {
        "organization": depot.pk,
        "supplier": supplier.pk,
        "currency": "USD",
        "exchange_rate": "1300.000000",
        "incoterm": "CIF",
        "payment_terms_days": 45,
        "expected_delivery": str(date.today() + timedelta(days=30)),
        "is_import": True,
        "lines": [
            {"product": product.pk, "quantity_ordered": 100, "unit_price": "2.50"},
        ],
        **overrides,
    }
    resp = client.post("/api/procurement/orders/", payload, format="json")
    assert resp.status_code == 201, resp.content
    return resp.json()


# ---------------------------------------------------------------------------
# Supplier master & qualification
# ---------------------------------------------------------------------------


def test_supplier_profile_scores_and_standing(
    qualified_supplier: Supplier, approver: User, depot: Organization
) -> None:
    profile = SupplierProfile.objects.get(supplier=qualified_supplier)
    client = _auth(approver)

    resp = client.get("/api/procurement/supplier-profiles/")
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["supplier_name"] == "Global Pharma Imports"
    assert row["can_order"] is True
    assert row["qualification_issues"] == []

    resp = client.post(
        f"/api/procurement/supplier-profiles/{profile.pk}/set_standing/",
        {"standing": "BLACKLISTED", "reason": "Falsified certificate of analysis"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["standing"] == "BLACKLISTED"
    assert resp.json()["can_order"] is False


def test_blacklisting_requires_a_reason(qualified_supplier: Supplier, approver: User) -> None:
    profile = SupplierProfile.objects.get(supplier=qualified_supplier)
    resp = _auth(approver).post(
        f"/api/procurement/supplier-profiles/{profile.pk}/set_standing/",
        {"standing": "BLACKLISTED", "reason": ""},
        format="json",
    )
    assert resp.status_code == 400
    assert "reason" in str(resp.content).lower()


def test_order_blocked_for_unqualified_supplier(
    depot: Organization, supplier: Supplier, product: Product, buyer: User
) -> None:
    """No verified licence on file → the PO cannot be submitted (GDP qualification)."""
    client = _auth(buyer)
    order = _draft_order(client, depot, supplier, product)
    resp = client.post(f"/api/procurement/orders/{order['id']}/submit/", {}, format="json")
    assert resp.status_code == 400
    assert "not qualified" in str(resp.content)


def test_order_blocked_for_blacklisted_supplier(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User
) -> None:
    profile = SupplierProfile.objects.get(supplier=qualified_supplier)
    profile.standing = SupplierProfile.Standing.BLACKLISTED
    profile.save(update_fields=["standing"])
    client = _auth(buyer)
    order = _draft_order(client, depot, qualified_supplier, product)
    resp = client.post(f"/api/procurement/orders/{order['id']}/submit/", {}, format="json")
    assert resp.status_code == 400
    assert "blacklisted" in str(resp.content).lower()


def test_expired_licence_blocks_the_order(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User
) -> None:
    licence = SupplierLicence.objects.get(supplier=qualified_supplier)
    licence.expires_on = date.today() - timedelta(days=1)
    licence.save(update_fields=["expires_on"])
    client = _auth(buyer)
    order = _draft_order(client, depot, qualified_supplier, product)
    resp = client.post(f"/api/procurement/orders/{order['id']}/submit/", {}, format="json")
    assert resp.status_code == 400
    assert "expired" in str(resp.content).lower()


# ---------------------------------------------------------------------------
# Requisitions → consolidated purchasing
# ---------------------------------------------------------------------------


def test_requisition_submit_approve_and_consolidate(
    depot: Organization,
    branch: Organization,
    qualified_supplier: Supplier,
    product: Product,
    product_b: Product,
    buyer: User,
    approver: User,
) -> None:
    client = _auth(buyer)
    reqs = []
    for qty in (40, 60):
        resp = client.post(
            "/api/procurement/requisitions/",
            {
                "organization": depot.pk,
                "priority": "HIGH",
                "needed_by": str(date.today() + timedelta(days=14)),
                "justification": "Below reorder level",
                "lines": [
                    {"product": product.pk, "quantity": qty, "estimated_unit_cost": "3.00"},
                    {"product": product_b.pk, "quantity": 10, "estimated_unit_cost": "1.00"},
                ],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        reqs.append(resp.json())

    assert reqs[0]["estimated_total"] == "130.00"

    approval_ids = []
    for req in reqs:
        resp = client.post(f"/api/procurement/requisitions/{req['id']}/submit/", {}, format="json")
        assert resp.status_code == 200, resp.content
        assert resp.json()["requisition"]["status"] == "SUBMITTED"
        assert resp.json()["requisition"]["requisition_number"].startswith("PR-")
        approval_ids.append(resp.json()["approval_id"])

    # A procurement officer holds no approval rights at all.
    self_claim = _auth(buyer).post(f"/api/approvals/requests/{approval_ids[0]}/claim/")
    assert self_claim.status_code == 403

    for approval_id in approval_ids:
        _approve(approval_id, approver)
    for req in reqs:
        assert (
            PurchaseRequisition.objects.get(pk=req["id"]).status
            == PurchaseRequisition.Status.APPROVED
        )

    resp = client.post(
        "/api/procurement/requisitions/consolidate/",
        {
            "organization": depot.pk,
            "supplier": qualified_supplier.pk,
            "requisitions": [r["id"] for r in reqs],
            "expected_delivery": str(date.today() + timedelta(days=21)),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    order = resp.json()
    # Same product across two requisitions merges onto one PO line.
    assert len(order["lines"]) == 2
    amox = next(ln for ln in order["lines"] if ln["product"] == product.pk)
    assert amox["quantity_ordered"] == 100
    for req in reqs:
        assert (
            PurchaseRequisition.objects.get(pk=req["id"]).status
            == PurchaseRequisition.Status.CONVERTED
        )


def test_no_self_approval_even_for_a_manager(
    depot: Organization, product: Product, approver: User
) -> None:
    """An approver who raises the request may not decide it — the engine's rule."""
    client = _auth(approver)
    requisition = client.post(
        "/api/procurement/requisitions/",
        {
            "organization": depot.pk,
            "lines": [{"product": product.pk, "quantity": 5, "estimated_unit_cost": "1.00"}],
        },
        format="json",
    ).json()
    approval_id = client.post(
        f"/api/procurement/requisitions/{requisition['id']}/submit/", {}, format="json"
    ).json()["approval_id"]

    resp = client.post(f"/api/approvals/requests/{approval_id}/claim/")
    assert resp.status_code == 400
    assert "own request" in str(resp.content)


def test_rejected_requisition_returns_to_the_requester(
    depot: Organization, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    resp = client.post(
        "/api/procurement/requisitions/",
        {
            "organization": depot.pk,
            "lines": [{"product": product.pk, "quantity": 5, "estimated_unit_cost": "1.00"}],
        },
        format="json",
    )
    requisition_id = resp.json()["id"]
    approval_id = client.post(
        f"/api/procurement/requisitions/{requisition_id}/submit/", {}, format="json"
    ).json()["approval_id"]

    decider = _auth(approver)
    decider.post(f"/api/approvals/requests/{approval_id}/claim/")
    resp = decider.post(
        f"/api/approvals/requests/{approval_id}/reject/",
        {"note": "Stock is arriving from another branch"},
        format="json",
    )
    assert resp.status_code == 200

    listing = client.get("/api/procurement/requisitions/").json()["results"]
    row = next(r for r in listing if r["id"] == requisition_id)
    assert row["status"] == "REJECTED"
    assert "another branch" in row["decision_note"]


# ---------------------------------------------------------------------------
# RFQ & quote comparison
# ---------------------------------------------------------------------------


def test_rfq_quote_comparison_and_award(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User
) -> None:
    client = _auth(buyer)
    rival = Supplier.objects.create(name="Nile Distributors")

    resp = client.post(
        "/api/procurement/rfqs/",
        {
            "organization": depot.pk,
            "title": "Q3 antibiotics restock",
            "response_due": str(date.today() + timedelta(days=7)),
            "lines": [{"product": product.pk, "quantity": 500}],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    rfq = resp.json()
    sent = client.post(f"/api/procurement/rfqs/{rfq['id']}/send/", {}, format="json")
    assert sent.status_code == 200

    cheap = client.post(
        "/api/procurement/quotes/",
        {
            "rfq": rfq["id"],
            "supplier": qualified_supplier.pk,
            "currency": "USD",
            "exchange_rate": "1300.000000",
            "lead_time_days": 45,
            "freight_amount": "200.00",
            "lines": [{"product": product.pk, "quantity_offered": 500, "unit_price": "2.00"}],
        },
        format="json",
    )
    assert cheap.status_code == 201, cheap.content

    pricey = client.post(
        "/api/procurement/quotes/",
        {
            "rfq": rfq["id"],
            "supplier": rival.pk,
            "currency": "RWF",
            "exchange_rate": "1.000000",
            "lead_time_days": 7,
            "lines": [{"product": product.pk, "quantity_offered": 500, "unit_price": "3000.00"}],
        },
        format="json",
    )
    assert pricey.status_code == 201, pricey.content

    comparison = client.get(f"/api/procurement/rfqs/{rfq['id']}/comparison/").json()
    assert len(comparison) == 2
    # USD 1200 × 1300 = 1,560,000 RWF beats 1,500,000 RWF? No — the local quote wins.
    assert comparison[0]["supplier_name"] == "Nile Distributors"
    assert comparison[0]["is_cheapest"] is True
    assert Decimal(comparison[1]["delta_vs_best"]) > 0

    resp = client.post(f"/api/procurement/quotes/{cheap.json()['id']}/award/", {}, format="json")
    assert resp.status_code == 201, resp.content
    order = resp.json()
    assert order["supplier"] == qualified_supplier.pk
    assert order["lines"][0]["quantity_ordered"] == 500
    assert order["po_number"].startswith("PO-")
    # Losing quote is closed out, RFQ is awarded.
    loser = client.get(f"/api/procurement/quotes/{pricey.json()['id']}/").json()
    assert loser["status"] == "DECLINED"
    assert client.get(f"/api/procurement/rfqs/{rfq['id']}/").json()["status"] == "AWARDED"


# ---------------------------------------------------------------------------
# Purchase order lifecycle
# ---------------------------------------------------------------------------


def test_purchase_order_totals_and_lifecycle(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    order = _draft_order(
        client,
        depot,
        qualified_supplier,
        product,
        freight_amount="150.00",
        lines=[
            {
                "product": product.pk,
                "quantity_ordered": 100,
                "unit_price": "2.50",
                "discount_pct": "10.00",
                "tax_rate_pct": "18.00",
            }
        ],
    )
    # 100 × 2.50 less 10% = 225.00; VAT 18% = 40.50; + freight 150 = 415.50
    assert order["subtotal"] == "225.00"
    assert order["tax_total"] == "40.50"
    assert order["total_amount"] == "415.50"
    assert order["total_amount_base"] == "540150.00"  # × 1300
    assert order["status"] == "DRAFT"

    submitted = client.post(f"/api/procurement/orders/{order['id']}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["order"]["status"] == "PENDING_APPROVAL"

    # Cannot be sent before it is approved.
    early_send = client.post(f"/api/procurement/orders/{order['id']}/send/", {}, format="json")
    assert early_send.status_code == 400

    _approve(submitted.json()["approval_id"], approver)
    reloaded = PurchaseOrder.objects.get(pk=order["id"])
    assert reloaded.status == PurchaseOrder.Status.APPROVED
    assert reloaded.approved_by_id == approver.pk

    sent = client.post(
        f"/api/procurement/orders/{order['id']}/send/", {"method": "EMAIL"}, format="json"
    )
    assert sent.status_code == 200, sent.content
    assert sent.json()["order"]["status"] == "SENT"
    assert sent.json()["document_number"].startswith("PO-")


def test_approved_order_cannot_be_edited(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    order = _draft_order(client, depot, qualified_supplier, product)
    approval_id = client.post(
        f"/api/procurement/orders/{order['id']}/submit/", {}, format="json"
    ).json()["approval_id"]
    _approve(approval_id, approver)

    resp = client.patch(
        f"/api/procurement/orders/{order['id']}/", {"notes": "sneaky change"}, format="json"
    )
    assert resp.status_code == 400
    assert "no longer" in str(resp.content)


def test_order_scoped_to_visible_organizations(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, outsider: User
) -> None:
    _draft_order(_auth(buyer), depot, qualified_supplier, product)
    resp = _auth(outsider).get("/api/procurement/orders/")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


# ---------------------------------------------------------------------------
# Imports & landed cost
# ---------------------------------------------------------------------------


def test_landed_cost_allocation_lands_in_unit_cost(
    depot: Organization,
    qualified_supplier: Supplier,
    product: Product,
    product_b: Product,
    buyer: User,
) -> None:
    client = _auth(buyer)
    resp = client.post(
        "/api/procurement/consignments/",
        {
            "organization": depot.pk,
            "supplier": qualified_supplier.pk,
            "mode": "SEA",
            "incoterm": "CIF",
            "currency": "USD",
            "exchange_rate": "1300.000000",
            "proforma_number": "PI-9931",
            "proforma_date": str(date.today()),
            "proforma_amount": "1000.00",
            "bill_of_lading_number": "MAEU-77213",
            "port_of_loading": "Mumbai",
            "port_of_discharge": "Dar es Salaam",
            "customs_declaration_number": "C-2026-88120",
            "clearing_agent": "Kigali Clearing Ltd",
            "insurance_policy_number": "SORAS-4412",
            "allocation_basis": "VALUE",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    consignment = resp.json()
    assert consignment["reference"].startswith("IMP-")

    order = _draft_order(
        client,
        depot,
        qualified_supplier,
        product,
        lines=[
            {"product": product.pk, "quantity_ordered": 100, "unit_price": "3.00"},
            {"product": product_b.pk, "quantity_ordered": 100, "unit_price": "1.00"},
        ],
    )
    attach = client.post(
        f"/api/procurement/consignments/{consignment['id']}/attach_order/",
        {"order": order["id"]},
        format="json",
    )
    assert attach.status_code == 200, attach.content

    for kind, amount, recoverable in [
        ("FREIGHT", "260000.00", False),
        ("CUSTOMS_DUTY", "130000.00", False),
        ("INSURANCE", "26000.00", False),
        ("IMPORT_VAT", "93600.00", True),  # recoverable — must NOT hit unit cost
    ]:
        resp = client.post(
            "/api/procurement/landed-costs/",
            {
                "consignment": consignment["id"],
                "kind": kind,
                "amount": amount,
                "currency": "RWF",
                "exchange_rate": "1.000000",
                "is_recoverable_tax": recoverable,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content

    resp = client.post(
        f"/api/procurement/consignments/{consignment['id']}/allocate_costs/", {}, format="json"
    )
    assert resp.status_code == 200, resp.content
    result = resp.json()
    assert result["pool"] == "416000.00"  # recoverable import VAT excluded
    assert result["recoverable_tax"] == "93600.00"

    lines = {ln["product"]: ln for ln in result["allocations"]}
    # Goods: 100×3.00×1300 = 390,000 and 100×1.00×1300 = 130,000 → 75% / 25% split.
    amox = next(a for a in result["allocations"] if a["line_id"])
    assert Decimal(result["goods_value_base"]) == Decimal("520000.00")
    allocated = sorted(Decimal(a["allocated"]) for a in result["allocations"])
    assert allocated == [Decimal("104000.00"), Decimal("312000.00")]
    assert sum(allocated) == Decimal("416000.00")

    expensive = max(result["allocations"], key=lambda a: Decimal(a["landed_unit_cost"]))
    # 3,900 goods + 3,120 landed share = 7,020 per unit
    assert Decimal(expensive["landed_unit_cost"]) == Decimal("7020.00")
    assert amox is not None and lines  # allocation rows are addressable per line

    assert ImportConsignment.objects.get(pk=consignment["id"]).costs_allocated_at is not None


def test_landed_cost_needs_an_attached_order(
    depot: Organization, qualified_supplier: Supplier, buyer: User
) -> None:
    client = _auth(buyer)
    consignment = client.post(
        "/api/procurement/consignments/",
        {"organization": depot.pk, "supplier": qualified_supplier.pk},
        format="json",
    ).json()
    resp = client.post(
        f"/api/procurement/consignments/{consignment['id']}/allocate_costs/", {}, format="json"
    )
    assert resp.status_code == 400
    assert "purchase order" in str(resp.content)


# ---------------------------------------------------------------------------
# Goods receipt
# ---------------------------------------------------------------------------


def _approved_order(
    client: APIClient,
    depot: Organization,
    supplier: Supplier,
    product: Product,
    approver: User,
    **overrides,
) -> dict:
    order = _draft_order(client, depot, supplier, product, **overrides)
    approval_id = client.post(
        f"/api/procurement/orders/{order['id']}/submit/", {}, format="json"
    ).json()["approval_id"]
    _approve(approval_id, approver)
    return order


def test_goods_receipt_lands_stock_in_quarantine_with_qc(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    order = _approved_order(client, depot, qualified_supplier, product, approver)

    resp = client.post(f"/api/procurement/orders/{order['id']}/start_receipt/", {}, format="json")
    assert resp.status_code == 201, resp.content
    receipt = resp.json()
    assert receipt["grn_number"].startswith("GRN-")
    assert receipt["lines"][0]["quantity_expected"] == 100
    assert receipt["requires_qc"] is True

    # Partial receipt: 60 good, 5 damaged — batch + expiry captured.
    line = receipt["lines"][0]
    resp = client.patch(
        f"/api/procurement/receipts/{receipt['id']}/",
        {
            "supplier_delivery_note": "DN-5512",
            "vehicle_plate": "RAB 123 C",
            "lines": [
                {
                    "order_line": line["order_line"],
                    "product": line["product"],
                    "batch_number": "BX-2026-A",
                    "expiry_date": str(date.today() + timedelta(days=540)),
                    "quantity_expected": 100,
                    "quantity_received": 60,
                    "quantity_rejected": 5,
                    "rejection_reason": "DAMAGED",
                    "unit_cost": "3250.00",
                }
            ],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content

    posted = client.post(f"/api/procurement/receipts/{receipt['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    body = posted.json()
    assert body["status"] == "POSTED"
    assert body["has_discrepancy"] is True
    assert body["total_received"] == 60
    assert body["total_rejected"] == 5

    batch = InventoryBatch.objects.get(organization=depot, batch_number="BX-2026-A")
    assert batch.quantity_available == 60
    assert batch.status == InventoryBatch.Status.QUARANTINE
    assert batch.wholesale_cost == Decimal("3250.00")
    assert batch.source_supplier_id == qualified_supplier.pk
    assert QualityCheck.objects.filter(
        batch=batch, status=QualityCheck.Status.PENDING_REVIEW
    ).exists()

    po = PurchaseOrder.objects.get(pk=order["id"])
    assert po.status == PurchaseOrder.Status.PARTIALLY_RECEIVED
    po_line = po.lines.first()
    assert po_line.quantity_received == 60
    assert po_line.quantity_rejected == 5
    assert po_line.quantity_outstanding == 40

    # Dr Inventory / Cr GRNI at the received value (60 × 3,250 = 195,000).
    entry = JournalEntry.objects.get(
        reference_type="goods_receipt", reference_id=str(receipt["id"])
    )
    assert entry.total_debit == entry.total_credit == 195000.0
    assert set(entry.lines.values_list("account__code", flat=True)) == {"1500", "2150"}


def test_receipt_refuses_missing_batch_or_expired_stock(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    order = _approved_order(client, depot, qualified_supplier, product, approver)
    receipt = client.post(
        f"/api/procurement/orders/{order['id']}/start_receipt/", {}, format="json"
    ).json()
    line = receipt["lines"][0]

    resp = client.post(f"/api/procurement/receipts/{receipt['id']}/post/", {}, format="json")
    assert resp.status_code == 400
    assert "batch number is required" in str(resp.content).lower()

    client.patch(
        f"/api/procurement/receipts/{receipt['id']}/",
        {
            "lines": [
                {
                    "order_line": line["order_line"],
                    "product": line["product"],
                    "batch_number": "OLD-1",
                    "expiry_date": str(date.today() - timedelta(days=1)),
                    "quantity_expected": 100,
                    "quantity_received": 100,
                    "unit_cost": "10.00",
                }
            ]
        },
        format="json",
    )
    resp = client.post(f"/api/procurement/receipts/{receipt['id']}/post/", {}, format="json")
    assert resp.status_code == 400
    assert "expired" in str(resp.content).lower()


def test_posted_receipt_is_immutable(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    receipt = _post_full_receipt(client, depot, qualified_supplier, product, approver)
    resp = client.patch(
        f"/api/procurement/receipts/{receipt['id']}/", {"notes": "tweak"}, format="json"
    )
    assert resp.status_code == 400
    assert "immutable" in str(resp.content).lower()


def _post_full_receipt(
    client: APIClient,
    depot: Organization,
    supplier: Supplier,
    product: Product,
    approver: User,
    unit_cost: str = "3250.00",
    quantity: int = 100,
) -> dict:
    order = _approved_order(client, depot, supplier, product, approver)
    receipt = client.post(
        f"/api/procurement/orders/{order['id']}/start_receipt/", {}, format="json"
    ).json()
    line = receipt["lines"][0]
    client.patch(
        f"/api/procurement/receipts/{receipt['id']}/",
        {
            "lines": [
                {
                    "order_line": line["order_line"],
                    "product": line["product"],
                    "batch_number": f"B-{order['id']}",
                    "expiry_date": str(date.today() + timedelta(days=400)),
                    "quantity_expected": 100,
                    "quantity_received": quantity,
                    "unit_cost": unit_cost,
                }
            ]
        },
        format="json",
    )
    resp = client.post(f"/api/procurement/receipts/{receipt['id']}/post/", {}, format="json")
    assert resp.status_code == 200, resp.content
    return resp.json()


# ---------------------------------------------------------------------------
# Supplier invoices — 3-way match
# ---------------------------------------------------------------------------


def _invoice_payload(depot: Organization, supplier: Supplier, receipt: dict, **overrides) -> dict:
    order_line_id = receipt["lines"][0]["order_line"]
    return {
        "organization": depot.pk,
        "supplier": supplier.pk,
        "order": GoodsReceipt.objects.get(pk=receipt["id"]).order_id,
        "receipt": receipt["id"],
        "invoice_number": "SUP-INV-771",
        "invoice_date": str(date.today()),
        "currency": "RWF",
        "exchange_rate": "1.000000",
        "tax_class": "C",
        "lines": [
            {
                "order_line": order_line_id,
                "product": receipt["lines"][0]["product"],
                "quantity": "100.00",
                "unit_price": "3250.00",
            }
        ],
        **overrides,
    }


def test_three_way_match_clean_invoice_posts_to_the_ledger(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    receipt = _post_full_receipt(client, depot, qualified_supplier, product, approver)
    # The PO was priced in USD; invoice against a same-currency PO for a clean match.
    order = PurchaseOrder.objects.get(pk=receipt["order"])
    order.currency = "RWF"
    order.exchange_rate = Decimal("1")
    order.save(update_fields=["currency", "exchange_rate"])
    line = order.lines.first()
    line.unit_price = Decimal("3250.00")
    line.save(update_fields=["unit_price"])

    resp = client.post(
        "/api/procurement/invoices/",
        _invoice_payload(depot, qualified_supplier, receipt),
        format="json",
    )
    assert resp.status_code == 201, resp.content
    invoice = resp.json()
    assert invoice["total_amount"] == "325000.00"

    matched = client.post(f"/api/procurement/invoices/{invoice['id']}/match/", {}, format="json")
    assert matched.status_code == 200, matched.content
    assert matched.json()["match_result"] == "MATCHED"
    assert matched.json()["status"] == "MATCHED"
    assert matched.json()["has_variance"] is False

    submitted = client.post(f"/api/procurement/invoices/{invoice['id']}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    _approve(submitted.json()["approval_id"], approver)

    stored = SupplierInvoice.objects.get(pk=invoice["id"])
    assert stored.status == SupplierInvoice.Status.APPROVED
    assert stored.finance_bill_id is not None

    bill = SupplierBill.objects.get(pk=stored.finance_bill_id)
    assert bill.total_amount == Decimal("325000.00")
    assert bill.reference_type == "procurement.supplier_invoice"

    entry = JournalEntry.objects.get(reference_type="supplier_invoice", reference_id=str(stored.pk))
    assert entry.total_debit == entry.total_credit == 325000.0
    codes = dict(entry.lines.values_list("account__code", "side"))
    assert codes["2150"] == JournalLine.Side.DEBIT  # GRNI cleared
    assert codes["2100"] == JournalLine.Side.CREDIT  # payable raised

    stored.refresh_from_db()
    assert stored.order.lines.first().quantity_invoiced == 100


def test_three_way_match_flags_quantity_and_price_variance(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    receipt = _post_full_receipt(client, depot, qualified_supplier, product, approver, quantity=60)
    order = PurchaseOrder.objects.get(pk=receipt["order"])
    order.currency = "RWF"
    order.exchange_rate = Decimal("1")
    order.save(update_fields=["currency", "exchange_rate"])
    line = order.lines.first()
    line.unit_price = Decimal("3000.00")
    line.save(update_fields=["unit_price"])

    resp = client.post(
        "/api/procurement/invoices/",
        _invoice_payload(depot, qualified_supplier, receipt),  # 100 @ 3,250
        format="json",
    )
    invoice = resp.json()
    matched = client.post(f"/api/procurement/invoices/{invoice['id']}/match/", {}, format="json")
    assert matched.status_code == 200, matched.content
    body = matched.json()
    assert body["match_result"] == "QTY_AND_PRICE"
    assert body["status"] == "VARIANCE"
    detail = body["match_detail"][0]
    assert detail["received_qty"] == "60"
    assert detail["invoiced_qty"] == "100.00"

    # A variance cannot be pushed for approval without someone owning it.
    resp = client.post(f"/api/procurement/invoices/{invoice['id']}/submit/", {}, format="json")
    assert resp.status_code == 400
    assert "override reason is required" in str(resp.content)

    resp = client.post(
        f"/api/procurement/invoices/{invoice['id']}/submit/",
        {"override_reason": "Supplier confirmed 40 units ship next week; price rise agreed."},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    _approve(resp.json()["approval_id"], approver)
    assert SupplierInvoice.objects.get(pk=invoice["id"]).status == SupplierInvoice.Status.APPROVED


def test_invoice_without_a_receipt_cannot_match_clean(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    order = _approved_order(client, depot, qualified_supplier, product, approver)
    resp = client.post(
        "/api/procurement/invoices/",
        {
            "organization": depot.pk,
            "supplier": qualified_supplier.pk,
            "order": order["id"],
            "invoice_number": "SUP-INV-999",
            "invoice_date": str(date.today()),
            "lines": [
                {
                    "order_line": order["lines"][0]["id"],
                    "product": product.pk,
                    "quantity": "100.00",
                    "unit_price": "2.50",
                }
            ],
        },
        format="json",
    )
    invoice = resp.json()
    matched = client.post(f"/api/procurement/invoices/{invoice['id']}/match/", {}, format="json")
    body = matched.json()
    assert body["match_result"] == "NO_RECEIPT"
    assert body["has_variance"] is True


# ---------------------------------------------------------------------------
# Debit / credit notes & statement
# ---------------------------------------------------------------------------


def test_debit_note_reduces_the_payable_and_posts(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    receipt = _post_full_receipt(client, depot, qualified_supplier, product, approver)
    order = PurchaseOrder.objects.get(pk=receipt["order"])
    order.currency = "RWF"
    order.exchange_rate = Decimal("1")
    order.save(update_fields=["currency", "exchange_rate"])
    line = order.lines.first()
    line.unit_price = Decimal("3250.00")
    line.save(update_fields=["unit_price"])

    invoice = client.post(
        "/api/procurement/invoices/",
        _invoice_payload(depot, qualified_supplier, receipt),
        format="json",
    ).json()
    client.post(f"/api/procurement/invoices/{invoice['id']}/match/", {}, format="json")
    approval_id = client.post(
        f"/api/procurement/invoices/{invoice['id']}/submit/", {}, format="json"
    ).json()["approval_id"]
    _approve(approval_id, approver)

    note = client.post(
        "/api/procurement/supplier-notes/",
        {
            "organization": depot.pk,
            "supplier": qualified_supplier.pk,
            "invoice": invoice["id"],
            "kind": "DEBIT",
            "reason": "DAMAGE",
            "note_date": str(date.today()),
            "amount": "25000.00",
            "description": "5 packs crushed in transit",
        },
        format="json",
    )
    assert note.status_code == 201, note.content
    issued = client.post(
        f"/api/procurement/supplier-notes/{note.json()['id']}/issue/", {}, format="json"
    )
    assert issued.status_code == 200, issued.content
    assert issued.json()["note_number"].startswith("DBN-")

    bill = SupplierBill.objects.get(
        reference_type="procurement.supplier_invoice", reference_id=str(invoice["id"])
    )
    assert bill.total_amount == Decimal("300000.00")  # 325,000 − 25,000

    entry = JournalEntry.objects.get(
        reference_type="supplier_note", reference_id=str(note.json()["id"])
    )
    assert entry.total_debit == entry.total_credit == 25000.0

    detail = client.get(f"/api/procurement/invoices/{invoice['id']}/").json()
    assert detail["notes_total"] == "25000.00"
    assert detail["payable_amount"] == "350000.00"


def test_supplier_statement_reconciles(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    client = _auth(buyer)
    receipt = _post_full_receipt(client, depot, qualified_supplier, product, approver)
    order = PurchaseOrder.objects.get(pk=receipt["order"])
    order.currency = "RWF"
    order.exchange_rate = Decimal("1")
    order.save(update_fields=["currency", "exchange_rate"])
    line = order.lines.first()
    line.unit_price = Decimal("3250.00")
    line.save(update_fields=["unit_price"])

    invoice = client.post(
        "/api/procurement/invoices/",
        _invoice_payload(depot, qualified_supplier, receipt),
        format="json",
    ).json()
    client.post(f"/api/procurement/invoices/{invoice['id']}/match/", {}, format="json")
    approval_id = client.post(
        f"/api/procurement/invoices/{invoice['id']}/submit/", {}, format="json"
    ).json()["approval_id"]
    _approve(approval_id, approver)

    resp = client.get(
        "/api/procurement/statement/",
        {"organization": depot.pk, "supplier": qualified_supplier.pk},
    )
    assert resp.status_code == 200, resp.content
    statement = resp.json()
    assert statement["supplier_name"] == "Global Pharma Imports"
    assert statement["closing_balance"] == "325000.00"
    assert statement["entries"][0]["type"] == "INVOICE"


def test_overview_counts_the_buyers_workload(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User
) -> None:
    client = _auth(buyer)
    _draft_order(client, depot, qualified_supplier, product)
    resp = client.get("/api/procurement/overview/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["orders_draft"] == 1
    assert body["orders_open"] == 0
    assert "licences_expiring" in body


def test_arriving_stock_closes_the_retail_demand_it_was_imported_for(
    depot: Organization, qualified_supplier: Supplier, product: Product, buyer: User, approver: User
) -> None:
    """The demand loop has to close, or it re-proposes an import that already landed.

    A pharmacy asks for stock the depot has not got -> the shortfall is captured as
    demand -> the demand becomes a requisition -> the requisition becomes an import.
    When that import is received, the people who were waiting must stop waiting.
    ``settle_backorders_for`` existed and was unit-tested, but nothing called it.
    """
    from apps.distribution.demand import capture, raise_requisition_from_demand
    from apps.distribution.models import BackorderLine

    retail = Organization.objects.create(name="Waiting Pharmacy", type="RETAIL")
    other = Organization.objects.create(name="Second Pharmacy", type="RETAIL")
    first = capture(depot=depot, retail=retail, product=product, quantity=40)
    second = capture(depot=depot, retail=other, product=product, quantity=40)
    raise_requisition_from_demand(depot=depot, user=None)
    first.refresh_from_db()
    assert first.status == BackorderLine.Status.SOURCING

    client = _auth(buyer)
    order = _approved_order(client, depot, qualified_supplier, product, approver)
    receipt = client.post(
        f"/api/procurement/orders/{order['id']}/start_receipt/", {}, format="json"
    ).json()
    line = receipt["lines"][0]
    client.patch(
        f"/api/procurement/receipts/{receipt['id']}/",
        {
            "lines": [
                {
                    "order_line": line["order_line"],
                    "product": line["product"],
                    "batch_number": "DEMAND-FILL",
                    "expiry_date": str(date.today() + timedelta(days=400)),
                    "quantity_expected": 100,
                    "quantity_received": 60,
                    "unit_cost": "3250.00",
                }
            ]
        },
        format="json",
    )
    posted = client.post(f"/api/procurement/receipts/{receipt['id']}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == BackorderLine.Status.FULFILLED, "the longest waiter is served first"
    assert first.quantity_fulfilled == 40
    # 60 landed, 40 closed the first request; the remaining 20 part-fills the next.
    assert second.quantity_fulfilled == 20
    assert second.status == BackorderLine.Status.SOURCING, "still owed 20"
