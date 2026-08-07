"""Slice 3 — Tax, VAT, EBM fiscalization bridge.

Covers:
- TaxCode seeding (A/B/C/D + 2025-01-01 effective date).
- Supplier bill with VAT splits Dr Expense (net) / Dr VAT Input / Cr AP.
- record_tax_payment posts Dr VAT Output / Cr Cash & Bank.
- VAT return report computes Output - Input = payable per class.
- EBM mirror posts a confirming journal line for the SDC receipt.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from apps.catalog.models import Product, Supplier
from apps.finance.models import (
    JournalEntry,
    JournalLine,
    TaxCode,
    TaxRecord,
)
from apps.finance.reports import vat_return
from apps.finance.services import (
    ensure_default_accounts,
    mirror_ebm_to_ledger,
    record_supplier_bill,
    record_tax_payment,
)
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail.models import Sale, SaleItem
from apps.retail.services import complete_sale

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Tax Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def supplier(db: None) -> Supplier:
    return Supplier.objects.create(name="MediWholesale Rwanda")


@pytest.fixture
def product_b(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


@pytest.fixture
def listing_b(org: Organization, product_b: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=org, product=product_b, retail_price="1180.00"
    )


@pytest.fixture
def batch_b(org: Organization, product_b: Product) -> InventoryBatch:
    return InventoryBatch.objects.create(
        organization=org,
        product=product_b,
        batch_number="B-FEFO",
        expiry_date=date(2026, 12, 31),
        quantity_available=10,
        wholesale_cost=Decimal("700.00"),
    )


@pytest.fixture
def cashier(db: None, org: Organization) -> User:
    user = User.objects.create_user(username="cash_t", password="x")
    user.organization = org
    user.save(update_fields=["organization"])
    return user


# ---------------------------------------------------------------------------
# TaxCode seeding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_tax_codes_creates_four_classes(org: Organization) -> None:
    """The seed_tax_codes command should guarantee A/B/C/D rows dated 2025-01-01."""
    from django.core.management import call_command

    call_command("seed_tax_codes")
    codes = {c.code: c for c in TaxCode.objects.filter(organization=org)}
    assert set(codes) == {"A", "B", "C", "D"}
    assert codes["B"].rate_pct == Decimal("18.00")
    assert codes["B"].withholding_pct == Decimal("15.00")
    assert codes["C"].rate_pct == Decimal("0.00")  # zero-rated medicines
    assert all(c.effective_from == date(2025, 1, 1) for c in codes.values())


@pytest.mark.django_db
def test_tax_code_unique_on_effective_from(org: Organization) -> None:
    """Two rows with the same code + effective_from must not coexist."""
    from django.db import IntegrityError, transaction

    TaxCode.objects.create(
        organization=org, code="B", rate_pct=Decimal("18"), effective_from=date(2025, 1, 1)
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        TaxCode.objects.create(
            organization=org,
            code="B",
            rate_pct=Decimal("18"),
            effective_from=date(2025, 1, 1),
        )


# ---------------------------------------------------------------------------
# Supplier bill with VAT split
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_supplier_bill_with_vat_splits_three_lines(
    org: Organization,
    supplier: Supplier,
) -> None:
    """A 118,000 RWF bill with 18% VAT splits as:
    Dr Expense (net)    100,000
    Dr VAT Input         18,000
    Cr Accounts Payable 118,000
    """
    ensure_default_accounts(org)
    bill = record_supplier_bill(
        organization=org,
        supplier=supplier,
        bill_number="INV-2025-001",
        bill_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("118000.00"),
        vat_amount=Decimal("18000.00"),
        tax_class="B",
        user=None,
    )
    bill.refresh_from_db()
    assert bill.vat_amount == Decimal("18000.00")
    entry = JournalEntry.objects.get(reference_type="supplier_bill", reference_id=str(bill.pk))
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["5000"] == ("DEBIT", Decimal("100000.00"))
    assert lines["1350"] == ("DEBIT", Decimal("18000.00"))
    assert lines["2100"] == ("CREDIT", Decimal("118000.00"))


@pytest.mark.django_db
def test_supplier_bill_without_vat_posts_one_line(
    org: Organization,
    supplier: Supplier,
) -> None:
    """A zero-rated supplier (or VAT-exempt import) posts single-line Dr Expense / Cr AP."""
    record_supplier_bill(
        organization=org,
        supplier=supplier,
        bill_number="INV-2025-002",
        bill_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("50000.00"),
        vat_amount=Decimal("0"),
        tax_class="C",
        user=None,
    )
    entry = JournalEntry.objects.filter(reference_type="supplier_bill").latest("id")
    codes = {ln.account.code for ln in entry.lines.all()}
    assert "1350" not in codes  # no VAT Input line
    assert {"5000", "2100"}.issubset(codes)


@pytest.mark.django_db
def test_supplier_bill_rejects_vat_exceeding_total(
    org: Organization,
    supplier: Supplier,
) -> None:
    with pytest.raises(ValueError, match="vat_amount cannot exceed total_amount"):
        record_supplier_bill(
            organization=org,
            supplier=supplier,
            bill_number="INV-2025-BAD",
            bill_date=date.today(),
            due_date=date.today(),
            total_amount=Decimal("1000.00"),
            vat_amount=Decimal("2000.00"),
            user=None,
        )


# ---------------------------------------------------------------------------
# VAT output accumulates via POS sales
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_vat_output_accumulates_across_sales(
    org: Organization,
    product_b: Product,
    listing_b: PharmacyProduct,
    batch_b: InventoryBatch,
    cashier: User,
) -> None:
    """Each B-class sale adds 18% VAT Output on the GL control account."""
    ensure_default_accounts(org)
    for _ in range(3):
        sale = Sale.objects.create(organization=org, sale_number=f"TEST-{uuid.uuid4().hex[:8]}")
        SaleItem.objects.create(
            sale=sale,
            product=product_b,
            quantity=1,
            unit_price=Decimal("1180.00"),
            tax_rate=Decimal("18"),
        )
        complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "1180.00"}], user=cashier)

    output_total = sum(
        ln.amount for ln in JournalLine.objects.filter(account__code="2300", side="CREDIT")
    )
    assert output_total == Decimal("540.00")  # 3 × 180


# ---------------------------------------------------------------------------
# vat_return report
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_vat_return_computes_net_payable(
    org: Organization,
    product_b: Product,
    listing_b: PharmacyProduct,
    batch_b: InventoryBatch,
    supplier: Supplier,
    cashier: User,
) -> None:
    """After 1 sale (180 VAT Output) + 1 supplier bill (180 VAT Input):
    net_payable = 180 − 180 = 0."""
    ensure_default_accounts(org)
    sale = Sale.objects.create(organization=org, sale_number=f"TEST-{uuid.uuid4().hex[:8]}")
    SaleItem.objects.create(
        sale=sale,
        product=product_b,
        quantity=1,
        unit_price=Decimal("1180.00"),
        tax_rate=Decimal("18"),
    )
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "1180.00"}], user=cashier)
    record_supplier_bill(
        organization=org,
        supplier=supplier,
        bill_number="INV-VAT",
        bill_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("1180.00"),
        vat_amount=Decimal("180.00"),
        tax_class="B",
        user=None,
    )

    today = date.today()
    ret = vat_return(org, start=today, end=today)
    assert Decimal(ret["output_total"]) == Decimal("180.00")
    assert Decimal(ret["input_total"]) == Decimal("180.00")
    assert Decimal(ret["net_payable"]) == Decimal("0.00")
    assert Decimal(ret["running_carry_forward"]) == Decimal("0.00")  # 180 - 180


# ---------------------------------------------------------------------------
# record_tax_payment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tax_payment_posts_balanced_entry(org: Organization) -> None:
    """record_tax_payment: Dr VAT Output / Cr Cash & Bank."""
    ensure_default_accounts(org)
    payment = record_tax_payment(
        organization=org,
        paid_on=date.today(),
        period_start=date.today().replace(day=1),
        period_end=date.today(),
        amount=Decimal("50000.00"),
        method="BANK_TRANSFER",
        rra_reference="RRA-2025-XYZ",
        user=None,
    )
    assert payment.payment_number.startswith("TAX-")
    entry = JournalEntry.objects.get(reference_type="tax_payment", reference_id=str(payment.pk))
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["2300"] == ("DEBIT", Decimal("50000.00"))
    # BANK_TRANSFER settles out of 1200 Bank, not the cash drawer.
    assert lines["1200"] == ("CREDIT", Decimal("50000.00"))


@pytest.mark.django_db
def test_tax_payment_rejects_non_positive_amount(org: Organization) -> None:
    with pytest.raises(ValueError, match="Tax payment amount must be positive"):
        record_tax_payment(
            organization=org,
            paid_on=date.today(),
            period_start=date.today(),
            period_end=date.today(),
            amount=Decimal("0"),
            user=None,
        )


# ---------------------------------------------------------------------------
# EBM fiscalization bridge
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ebm_mirror_posts_vat_to_ledger(org: Organization) -> None:
    """A TaxRecord (EBM OSDC receipt) mirrors its class breakdown into the GL so
    the EBM register and the VAT Output ledger agree to the cent."""
    ensure_default_accounts(org)
    record = TaxRecord.objects.create(
        organization=org,
        receipt_number="EBM-2025-001",
        sdc_id="SDC-001",
        mrc_number="MRC-001",
        taxable_amount=Decimal("1000.00"),
        vat_amount=Decimal("180.00"),
        tax_class_a=Decimal("0.00"),
        tax_class_b=Decimal("180.00"),
        tax_class_c=Decimal("0.00"),
        qr_code_payload="qr-data",
    )
    entry = mirror_ebm_to_ledger(tax_record=record, user=None)
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["1400"] == ("DEBIT", Decimal("180.00"))
    assert lines["2300"] == ("CREDIT", Decimal("180.00"))


@pytest.mark.django_db
def test_ebm_mirror_rejects_zero_vat(org: Organization) -> None:
    """A TaxRecord with no VAT carries nothing to mirror — refuse rather than
    post a zero-line entry."""
    ensure_default_accounts(org)
    record = TaxRecord.objects.create(
        organization=org,
        receipt_number="EBM-ZERO",
        taxable_amount=Decimal("0"),
        vat_amount=Decimal("0"),
    )
    with pytest.raises(ValueError, match="no VAT to mirror"):
        mirror_ebm_to_ledger(tax_record=record, user=None)


# ---------------------------------------------------------------------------
# Approval-gated tax payment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tax_payment_routes_through_approval_inbox(
    org: Organization,
    cashier: User,
) -> None:
    """request_tax_payment returns an ApprovalRequest rather than posting
    directly — no surprise bank wires."""
    from apps.approvals.models import ApprovalRequest
    from apps.finance.services import request_tax_payment

    ensure_default_accounts(org)
    req = request_tax_payment(
        organization=org,
        requested_by=cashier,
        paid_on=date.today(),
        period_start=date.today().replace(day=1),
        period_end=date.today(),
        amount=Decimal("25000.00"),
        method="BANK_TRANSFER",
        reason="Monthly VAT remittance",
    )
    assert req.resource_type == "finance.tax_payment"
    assert req.status == ApprovalRequest.Status.PENDING
    # No journal entry yet — the senior must approve first.
    assert not JournalEntry.objects.filter(reference_type="tax_payment").exists()
