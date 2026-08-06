"""Slice 4 — Customer AR (B2B invoices + receipts + statements + dunning).

Covers:
- CustomerInvoice creation: Dr AR / Cr Sales Revenue (and Cr VAT Output).
- Credit-profile guard: on-hold refuses; over-limit refuses.
- CustomerReceipt: Dr Cash / Cr AR; rolls invoice to PAID.
- Overpayment creates a CustomerCredit (on-account liability).
- vat split on invoices respects class B (18%) vs class C (0%).
- ar_aging buckets open balances into 0/1-30/31-60/61-90/90+.
- statement_of_account derives opening + closing from GL truth.
- apply_dunning: 7/14/30/60-day ladder; L4 auto-holds the credit profile.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.finance.models import (
    Account,
    CreditProfile,
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    DunningNotice,
    JournalEntry,
    JournalLine,
)
from apps.finance.reports import ar_aging, statement_of_account
from apps.finance.services import (
    CreditHoldError,
    apply_dunning,
    record_customer_invoice,
    record_customer_receipt,
)
from apps.iam.models import Organization, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def creditor(db: None) -> Organization:
    return Organization.objects.create(
        name="Wholesale Depot", type=Organization.OrgType.DEPOT
    )


@pytest.fixture
def debtor(db: None) -> Organization:
    return Organization.objects.create(
        name="Retail Buyer", type=Organization.OrgType.RETAIL
    )


@pytest.fixture
def credit_profile(db: None, creditor: Organization, debtor: Organization) -> CreditProfile:
    return CreditProfile.objects.create(
        creditor=creditor, debtor=debtor,
        credit_limit=Decimal("500000.00"), terms_days=30,
    )


@pytest.fixture
def cashier(db: None, creditor: Organization) -> User:
    user = User.objects.create_user(username="cashier_ar", password="x")
    user.organization = creditor
    user.save(update_fields=["organization"])
    return user


# ---------------------------------------------------------------------------
# CustomerInvoice creation + auto-posting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_invoice_posts_balanced_ar_entry(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    """A 118,000 RWF invoice with 18% VAT splits:
        Dr Accounts Receivable  118,000
        Cr Sales Revenue        100,000  (net of VAT)
        Cr VAT Output            18,000
    """
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("118000.00"), vat_amount=Decimal("18000.00"),
        tax_class="B", user=cashier,
    )
    inv.refresh_from_db()
    assert inv.invoice_number.startswith("INV-")
    entry = JournalEntry.objects.get(reference_type="customer_invoice", reference_id=str(inv.pk))
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    assert lines["1400"] == ("DEBIT", Decimal("118000.00"))
    assert lines["4100"] == ("CREDIT", Decimal("100000.00"))
    assert lines["2300"] == ("CREDIT", Decimal("18000.00"))


@pytest.mark.django_db
def test_zero_rated_invoice_skips_vat_line(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    """Class C (zero-rated medicines): no VAT Output line."""
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("50000.00"), vat_amount=Decimal("0"),
        tax_class="C", user=cashier,
    )
    entry = JournalEntry.objects.filter(reference_type="customer_invoice").latest("id")
    codes = {ln.account.code for ln in entry.lines.all()}
    assert "2300" not in codes  # no VAT Output
    assert {"1400", "4100"}.issubset(codes)


@pytest.mark.django_db
def test_invoice_rejects_non_positive_total(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    with pytest.raises(ValueError, match="Invoice total must be positive"):
        record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=date.today(), due_date=date.today(),
            total_amount=Decimal("0"), user=cashier,
        )


@pytest.mark.django_db
def test_invoice_rejects_vat_above_total(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    with pytest.raises(ValueError, match="vat_amount must be between 0 and total_amount"):
        record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=date.today(), due_date=date.today(),
            total_amount=Decimal("1000"), vat_amount=Decimal("2000"),
            user=cashier,
        )


# ---------------------------------------------------------------------------
# Credit-profile guard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_on_hold_credit_profile_blocks_invoice(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    credit_profile.status = CreditProfile.Status.HOLD
    credit_profile.hold_reason = "Test hold"
    credit_profile.save(update_fields=["status", "hold_reason"])
    with pytest.raises(CreditHoldError, match="on credit hold"):
        record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            total_amount=Decimal("100000"), user=cashier,
        )


@pytest.mark.django_db
def test_invoice_above_credit_limit_blocked(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    """Limit 500k; a single 600k invoice must be refused."""
    with pytest.raises(CreditHoldError, match="credit limit breached"):
        record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            total_amount=Decimal("600000"), user=cashier,
        )


@pytest.mark.django_db
def test_running_outstanding_accumulates_against_limit(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    """Two 300k invoices (600k total) exceed a 500k limit; the second must refuse."""
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("300000"), user=cashier,
    )
    with pytest.raises(CreditHoldError, match="credit limit breached"):
        record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            total_amount=Decimal("300000"), user=cashier,
        )


# ---------------------------------------------------------------------------
# CustomerReceipt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_full_payment_rolls_invoice_to_paid(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100000"), vat_amount=Decimal("0"),
        user=cashier,
    )
    receipt = record_customer_receipt(
        invoice=inv, amount=Decimal("100000"), method="BANK_TRANSFER",
        reference="RCP-001", user=cashier,
    )
    inv.refresh_from_db()
    assert inv.amount_paid == Decimal("100000")
    assert inv.status == CustomerInvoice.Status.PAID
    entry = JournalEntry.objects.get(reference_type="customer_receipt", reference_id=str(receipt.pk))
    lines = {ln.account.code: (ln.side, ln.amount) for ln in entry.lines.all()}
    # A bank transfer lands in 1200 Bank, not 1100 Cash on Hand — the debit
    # follows the tender the customer actually used.
    assert lines["1200"] == ("DEBIT", Decimal("100000"))
    assert lines["1400"] == ("CREDIT", Decimal("100000"))


@pytest.mark.django_db
def test_partial_payment_keeps_invoice_open(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100000"), user=cashier,
    )
    record_customer_receipt(
        invoice=inv, amount=Decimal("40000"), method="MOBILE_MONEY",
        user=cashier,
    )
    inv.refresh_from_db()
    assert inv.status == CustomerInvoice.Status.PARTIAL
    assert inv.amount_due == Decimal("60000")


@pytest.mark.django_db
def test_overpayment_creates_on_account_credit(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100000"), user=cashier,
    )
    record_customer_receipt(
        invoice=inv, amount=Decimal("120000"), method="BANK_TRANSFER",
        reference="OVERPAY", user=cashier,
    )
    inv.refresh_from_db()
    assert inv.status == CustomerInvoice.Status.PAID
    credit = CustomerCredit.objects.get(customer=debtor)
    assert credit.amount == Decimal("20000")
    assert credit.balance == Decimal("20000")


@pytest.mark.django_db
def test_receipt_rejects_non_positive_amount(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100000"), user=cashier,
    )
    with pytest.raises(ValueError, match="Receipt amount must be positive"):
        record_customer_receipt(invoice=inv, amount=Decimal("0"), user=cashier)


@pytest.mark.django_db
def test_receipt_refuses_already_paid_invoice(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100000"), user=cashier,
    )
    record_customer_receipt(invoice=inv, amount=Decimal("100000"), user=cashier)
    with pytest.raises(ValueError, match="already paid in full"):
        record_customer_receipt(invoice=inv, amount=Decimal("10000"), user=cashier)


# ---------------------------------------------------------------------------
# AR aging report
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_aging_buckets_open_invoices_by_days_past_due(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    today = date.today()
    # Current: due in 10 days (not yet overdue)
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=20), due_date=today + timedelta(days=10),
        total_amount=Decimal("50000"), user=cashier,
    )
    # 1-30: 15 days past due
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=45), due_date=today - timedelta(days=15),
        total_amount=Decimal("30000"), user=cashier,
    )
    # 31-60: 45 days past due
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=75), due_date=today - timedelta(days=45),
        total_amount=Decimal("20000"), user=cashier,
    )
    # 90+: 100 days past due
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=130), due_date=today - timedelta(days=100),
        total_amount=Decimal("10000"), user=cashier,
    )
    aging = ar_aging(creditor, as_of=today)
    assert aging["totals"]["current"] == Decimal("50000.00")
    assert aging["totals"]["days_1_30"] == Decimal("30000.00")
    assert aging["totals"]["days_31_60"] == Decimal("20000.00")
    assert aging["totals"]["days_90_plus"] == Decimal("10000.00")
    assert aging["totals"]["outstanding"] == Decimal("110000.00")


@pytest.mark.django_db
def test_aging_excludes_paid_invoices(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=date.today() - timedelta(days=50), due_date=date.today() - timedelta(days=20),
        total_amount=Decimal("100000"), user=cashier,
    )
    record_customer_receipt(invoice=inv, amount=Decimal("100000"), user=cashier)
    aging = ar_aging(creditor, as_of=date.today())
    assert aging["totals"]["outstanding"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# Statement of account
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_statement_opening_plus_lines_equals_closing(
    creditor: Organization, debtor: Organization, cashier: User,
) -> None:
    today = date.today()
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=10), due_date=today + timedelta(days=20),
        total_amount=Decimal("100000"), user=cashier,
    )
    record_customer_receipt(
        invoice=inv, amount=Decimal("40000"), received_on=today,
        user=cashier,
    )
    start = today - timedelta(days=30)
    end = today
    stmt = statement_of_account(creditor, debtor, start=start, end=end)
    assert stmt["customer_name"] == debtor.name
    assert stmt["opening_balance"] == Decimal("0.00")
    assert stmt["closing_balance"] == Decimal("60000.00")
    kinds = [ln["kind"] for ln in stmt["lines"]]
    assert "INVOICE" in kinds and "RECEIPT" in kinds


# ---------------------------------------------------------------------------
# Dunning ladder
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dunning_sends_reminder_at_7_days(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    today = date.today()
    inv = record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=37), due_date=today - timedelta(days=7),
        total_amount=Decimal("100000"), user=cashier,
    )
    notices = apply_dunning(organization=creditor, today=today)
    assert len(notices) == 1
    assert notices[0].level == DunningNotice.Level.REMINDER
    assert notices[0].invoice_id == inv.pk
    inv.refresh_from_db()
    assert inv.status == CustomerInvoice.Status.OVERDUE


@pytest.mark.django_db
def test_dunning_ladder_progression_by_days_past_due(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    today = date.today()
    cases = [
        (8, DunningNotice.Level.REMINDER),
        (16, DunningNotice.Level.SECOND),
        (35, DunningNotice.Level.FINAL),
        (75, DunningNotice.Level.LEGAL),
    ]
    for days_past, expected_level in cases:
        inv = record_customer_invoice(
            organization=creditor, customer=debtor,
            invoice_date=today - timedelta(days=days_past + 30),
            due_date=today - timedelta(days=days_past),
            total_amount=Decimal("50000"), user=cashier,
        )
        notices = apply_dunning(organization=creditor, today=today)
        assert any(n.level == expected_level and n.invoice_id == inv.pk for n in notices), (
            f"Expected level {expected_level} for {days_past} days past due"
        )


@pytest.mark.django_db
def test_dunning_legal_level_auto_holds_credit_profile(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    today = date.today()
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=120), due_date=today - timedelta(days=75),
        total_amount=Decimal("200000"), user=cashier,
    )
    apply_dunning(organization=creditor, today=today)
    credit_profile.refresh_from_db()
    assert credit_profile.status == CreditProfile.Status.HOLD
    assert "60+ days overdue" in credit_profile.hold_reason


@pytest.mark.django_db
def test_dunning_is_idempotent_same_day(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    today = date.today()
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=50), due_date=today - timedelta(days=20),
        total_amount=Decimal("75000"), user=cashier,
    )
    first = apply_dunning(organization=creditor, today=today)
    second = apply_dunning(organization=creditor, today=today)
    assert len(first) == 1
    assert len(second) == 0


@pytest.mark.django_db
def test_dunning_skips_invoices_under_7_days_past_due(
    creditor: Organization, debtor: Organization, credit_profile: CreditProfile, cashier: User,
) -> None:
    today = date.today()
    record_customer_invoice(
        organization=creditor, customer=debtor,
        invoice_date=today - timedelta(days=33), due_date=today - timedelta(days=3),
        total_amount=Decimal("40000"), user=cashier,
    )
    notices = apply_dunning(organization=creditor, today=today)
    assert notices == []
