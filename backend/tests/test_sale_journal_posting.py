"""Slice 2 — auto-posting POS sales into the GL.

Verifies that completing a retail sale produces balanced journal entries on
the organization's books: cash/revenue + VAT split on one entry, COGS/Inventory
on a second entry at the FEFO batch's wholesale cost. Also verifies stock-
count variances and wastage writeoffs hit the GL correctly.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.models import JournalEntry
from apps.finance.services import (
    ensure_default_accounts,
    post_inventory_adjustment,
)
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.inventory.services import log_wastage
from apps.retail.models import Sale, SaleItem
from apps.retail.services import complete_sale

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="City Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def product_b(db: None) -> Product:
    # 18% VAT class — VAT Output leg should fire on sales.
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


@pytest.fixture
def product_a(db: None) -> Product:
    # 0% VAT class (zero-rated medicine) — no VAT Output leg.
    return Product.objects.create(generic_name="ORS", strength="20.5g", tax_class="A")


@pytest.fixture
def listing_b(org: Organization, product_b: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=org, product=product_b, retail_price="1180.00"  # 1000 net + 180 VAT
    )


@pytest.fixture
def listing_a(org: Organization, product_a: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=org, product=product_a, retail_price="500.00"
    )


@pytest.fixture
def batch_b(org: Organization, product_b: Product) -> InventoryBatch:
    return InventoryBatch.objects.create(
        organization=org,
        product=product_b,
        batch_number="B-2025-01",
        expiry_date=date.today() + timedelta(days=300),
        quantity_available=10,
        wholesale_cost=Decimal("700.00"),
    )


@pytest.fixture
def cashier(db: None, org: Organization) -> User:
    user = User.objects.create_user(username="cash1", password="x")
    user.organization = org
    user.save(update_fields=["organization"])
    return user


def _open_sale(org: Organization, product: Product, qty: int) -> Sale:
    # sale_number has a unique constraint; assign a unique stub so we can
    # create several sales in the same test without a viewset roundtrip.
    import uuid

    sale = Sale.objects.create(organization=org, sale_number=f"TEST-{uuid.uuid4().hex[:8]}")
    SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=qty,
        unit_price=Decimal("1180.00") if product.tax_class == "B" else Decimal("500.00"),
        tax_rate=Decimal("18") if product.tax_class == "B" else Decimal("0"),
    )
    return sale


# ---------------------------------------------------------------------------
# post_sale_journal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sale_with_vat_posts_balanced_entries(
    org: Organization,
    product_b: Product,
    listing_b: PharmacyProduct,
    batch_b: InventoryBatch,
    cashier: User,
) -> None:
    """A B-class (18%) sale posts:
    Entry 1 (revenue):  Dr Cash 1180  / Cr Revenue 1000 + Cr VAT 180
    Entry 2 (COGS):     Dr COGS 700    / Cr Inventory 700   (1 unit × wholesale)
    """
    ensure_default_accounts(org)
    sale = _open_sale(org, product_b, qty=1)
    complete_sale(
        sale=sale,
        payments=[{"method": "CASH", "amount": "1180.00"}],
        user=cashier,
    )

    entries = list(JournalEntry.objects.filter(organization=org).order_by("id"))
    assert len(entries) == 2, [e.description for e in entries]

    revenue_entry, cogs_entry = entries
    rev_lines = {ln.account.code: (ln.side, ln.amount) for ln in revenue_entry.lines.all()}
    assert rev_lines["1100"] == ("DEBIT", Decimal("1180.00"))
    assert rev_lines["4100"] == ("CREDIT", Decimal("1000.00"))
    assert rev_lines["2300"] == ("CREDIT", Decimal("180.00"))

    cogs_lines = {ln.account.code: (ln.side, ln.amount) for ln in cogs_entry.lines.all()}
    assert cogs_lines["5000"] == ("DEBIT", Decimal("700.00"))
    assert cogs_lines["1500"] == ("CREDIT", Decimal("700.00"))


@pytest.mark.django_db
def test_zero_rated_sale_posts_no_vat_line(
    org: Organization,
    product_a: Product,
    listing_a: PharmacyProduct,
    cashier: User,
) -> None:
    """A-class medicine (0% VAT) — full sale goes to Sales Revenue, no VAT Output."""
    InventoryBatch.objects.create(
        organization=org,
        product=product_a,
        batch_number="A-2025-01",
        expiry_date=date.today() + timedelta(days=300),
        quantity_available=5,
        wholesale_cost=Decimal("250.00"),
    )
    sale = _open_sale(org, product_a, qty=2)
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "1000.00"}], user=cashier)

    entries = list(JournalEntry.objects.filter(organization=org).order_by("id"))
    assert len(entries) == 2
    revenue_lines = {ln.account.code for ln in entries[0].lines.all()}
    # 2050 VAT Output must NOT appear for a zero-rated line.
    assert "2300" not in revenue_lines
    assert {"1100", "4100"}.issubset(revenue_lines)


@pytest.mark.django_db
def test_journal_balances_for_every_sale_post(
    org: Organization,
    product_b: Product,
    listing_b: PharmacyProduct,
    batch_b: InventoryBatch,
    cashier: User,
) -> None:
    """Every posted journal entry must balance (Σdebits = Σcredits) — the
    leader's cockpit only works if the books are in order."""
    for qty in (1, 3, 5):
        sale = _open_sale(org, product_b, qty=qty)
        complete_sale(
            sale=sale, payments=[{"method": "CASH", "amount": str(qty * 1180)}], user=cashier
        )

    for entry in JournalEntry.objects.filter(organization=org):
        debits = sum(ln.amount for ln in entry.lines.all() if ln.side == "DEBIT")
        credits = sum(ln.amount for ln in entry.lines.all() if ln.side == "CREDIT")
        assert debits == credits, f"Unbalanced: {entry.description} D={debits} C={credits}"


@pytest.mark.django_db
def test_period_closed_blocks_sale_posting(
    org: Organization,
    product_b: Product,
    listing_b: PharmacyProduct,
    batch_b: InventoryBatch,
    cashier: User,
) -> None:
    """A sale can't post inside a closed period — closes must be final."""
    from apps.finance.models import AccountingPeriod
    from apps.finance.services import PeriodClosedError

    today = date.today()
    AccountingPeriod.objects.create(
        organization=org,
        kind=AccountingPeriod.Kind.MONTH,
        start_date=today.replace(day=1),
        end_date=today,
        status=AccountingPeriod.Status.CLOSED,
    )
    sale = _open_sale(org, product_b, qty=1)
    with pytest.raises(PeriodClosedError):
        complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "1180.00"}], user=cashier)


# ---------------------------------------------------------------------------
# post_inventory_adjustment (stock-count variance)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_positive_variance_reverses_cogs(
    org: Organization,
    batch_b: InventoryBatch,
) -> None:
    """Found stock (positive delta): Dr Inventory / Cr COGS — a gain."""
    ensure_default_accounts(org)
    batch_b.wholesale_cost = Decimal("700.00")
    batch_b.save(update_fields=["wholesale_cost"])

    post_inventory_adjustment(
        batch=batch_b,
        delta=2,
        unit_cost=None,
        reason="Stock count SC-001 found 2 extra",
        reference_type="stock_count",
        reference_id="1",
        user=None,
    )

    entry = JournalEntry.objects.get(organization=org, reference_type="stock_count")
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["1500"] == ("DEBIT", Decimal("1400.00"))
    assert lines["5000"] == ("CREDIT", Decimal("1400.00"))


@pytest.mark.django_db
def test_negative_variance_books_shrinkage(
    org: Organization,
    batch_b: InventoryBatch,
) -> None:
    """Missing stock (negative delta): Dr COGS / Cr Inventory — shrinkage expense."""
    ensure_default_accounts(org)
    post_inventory_adjustment(
        batch=batch_b,
        delta=-3,
        unit_cost=None,
        reason="Stock count SC-002 — 3 missing",
        reference_type="stock_count",
        reference_id="2",
        user=None,
    )
    entry = JournalEntry.objects.get(organization=org, reference_type="stock_count")
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["5000"] == ("DEBIT", Decimal("2100.00"))
    assert lines["1500"] == ("CREDIT", Decimal("2100.00"))


# ---------------------------------------------------------------------------
# post_writeoff (log_wastage)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_wastage_auto_posts_writeoff(
    org: Organization,
    batch_b: InventoryBatch,
) -> None:
    """log_wastage reduces on-hand AND posts Dr Inventory Adjustment / Cr Inventory."""
    ensure_default_accounts(org)
    log_wastage(
        batch=batch_b,
        quantity=2,
        reason="Expired lot",
        reference_type="wastage",
        reference_id="W-1",
        user=None,
    )
    batch_b.refresh_from_db()
    assert batch_b.quantity_available == 8

    entry = JournalEntry.objects.get(organization=org, reference_type="wastage")
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["5100"] == ("DEBIT", Decimal("1400.00"))
    assert lines["1500"] == ("CREDIT", Decimal("1400.00"))


# ---------------------------------------------------------------------------
# inventory_value + stock_turns KPIs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inventory_valuation_and_stock_turns(
    org: Organization,
    batch_b: InventoryBatch,
    cashier: User,
    listing_b: PharmacyProduct,
) -> None:
    """On-hand × wholesale_cost flows into the performance cockpit."""
    from apps.finance.reports import _inventory_value, performance

    ensure_default_accounts(org)
    assert _inventory_value(org) == Decimal("7000.00")  # 10 × 700

    # After a sale: 1 unit sold → inventory drops by 1 × 700 = 700.
    sale = _open_sale(org, batch_b.product, qty=1)
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "1180.00"}], user=cashier)
    assert _inventory_value(org) == Decimal("6300.00")  # 9 × 700

    today = date.today()
    perf = performance(org, start=today, end=today)
    assert Decimal(str(perf["inventory_value"])) == Decimal("6300.00")
    assert Decimal(str(perf["cash_on_hand"])) >= Decimal("0.00")  # 1000 control account exists
