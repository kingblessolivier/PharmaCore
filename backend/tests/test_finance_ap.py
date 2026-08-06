"""AP: supplier bills, payments, and their GL postings (Dr expense/Cr AP on the
bill; Dr AP/Cr Cash on payment)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.catalog.models import Supplier
from apps.finance.models import JournalEntry, SupplierBill
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Central Depot", type="DEPOT")


@pytest.fixture
def supplier(db: None) -> Supplier:
    return Supplier.objects.create(name="Global Pharma Imports")


@pytest.fixture
def accountant(org: Organization) -> User:
    u = User.objects.create_user(username="apclerk", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return u


@pytest.mark.django_db
def test_create_supplier_bill_posts_journal(
    org: Organization, supplier: Supplier, accountant: User
) -> None:
    resp = _auth(accountant).post(
        "/api/finance/supplier-bills/",
        {
            "organization": org.pk,
            "supplier": supplier.pk,
            "bill_number": "INV-2001",
            "bill_date": "2026-01-10",
            "due_date": "2026-02-10",
            "total_amount": "500000",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    bill_id = resp.json()["id"]
    assert resp.json()["status"] == "UNPAID"
    assert resp.json()["amount_due"] == "500000.00"

    entries = JournalEntry.objects.filter(
        organization=org, reference_type="supplier_bill", reference_id=str(bill_id)
    )
    assert entries.count() == 1
    assert entries.first().total_debit == 500000.0


@pytest.mark.django_db
def test_record_payment_rolls_up_status_and_posts_journal(
    org: Organization, supplier: Supplier, accountant: User
) -> None:
    bill = SupplierBill.objects.create(
        organization=org,
        supplier=supplier,
        bill_date=date(2026, 1, 10),
        total_amount=Decimal("200000"),
    )
    resp = _auth(accountant).post(
        f"/api/finance/supplier-bills/{bill.pk}/record-payment/",
        {"amount": "120000", "method": "BANK_TRANSFER", "reference": "TXN9"},
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "PARTIAL"
    assert resp.json()["amount_due"] == "80000.00"

    resp2 = _auth(accountant).post(
        f"/api/finance/supplier-bills/{bill.pk}/record-payment/",
        {"amount": "80000", "method": "BANK_TRANSFER", "reference": "TXN10"},
    )
    assert resp2.json()["status"] == "PAID"
    assert resp2.json()["amount_due"] == "0.00"

    payment_entries = JournalEntry.objects.filter(
        organization=org,
        reference_type="supplier_bill",
        reference_id=str(bill.pk),
        description__icontains="Payment",
    )
    assert payment_entries.count() == 2


@pytest.mark.django_db
def test_bills_scoped_to_visible_organizations(
    org: Organization, supplier: Supplier, accountant: User
) -> None:
    other_org = Organization.objects.create(name="Other Depot", type="DEPOT")
    SupplierBill.objects.create(
        organization=org,
        supplier=supplier,
        bill_date=date(2026, 1, 1),
        total_amount=Decimal("1000"),
    )
    SupplierBill.objects.create(
        organization=other_org,
        supplier=supplier,
        bill_date=date(2026, 1, 1),
        total_amount=Decimal("2000"),
    )
    resp = _auth(accountant).get("/api/finance/supplier-bills/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
