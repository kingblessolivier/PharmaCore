"""Pharmacy finance analytics — the maths, not the plumbing.

These assert the numbers a finance head would recompute by hand: that gross
margin only counts cost of sales, that EBITDA adds back interest and tax rather
than pretending they are operating costs, that the cash conversion cycle nets the
three components the right way round, and that expiring stock produces the
provision IAS 2 implies.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.models import Account, JournalLine
from apps.finance.pharmacy import (
    break_even,
    capital_returns,
    inventory_expiry_exposure,
    working_capital_cycle,
)
from apps.finance.reports import balance_sheet, profit_and_loss, trial_balance
from apps.finance.services import ensure_default_accounts, post_journal
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Nyarugenge Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


def _post(org: Organization, lines: list[tuple[str, str, str]], when: date = PERIOD_END) -> None:
    """Post a balanced entry from (code, side, amount) triples."""
    accounts = ensure_default_accounts(org)
    post_journal(
        organization=org,
        entry_date=when,
        description="test",
        lines=[
            {
                "account": accounts[code],
                "side": side,
                "amount": Decimal(amount),
                "memo": "",
            }
            for code, side, amount in lines
        ],
    )


def _trade(org: Organization, *, buy: str = "900000") -> None:
    """A month of trading, posted the way it really happens.

    Stock is bought *before* it is sold — posting cost of sales against an
    inventory account that was never debited leaves a negative asset, which is
    not a scenario worth measuring ratios against.
    """
    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    _post(org, [("1500", D, buy), ("2100", C, buy)], when=PERIOD_START)  # stock in, on credit
    _post(org, [("1100", D, "1000000"), ("4100", C, "1000000")])  # revenue
    _post(org, [("5000", D, "600000"), ("1500", C, "600000")])  # cost of sales
    _post(org, [("6100", D, "200000"), ("1100", C, "200000")])  # salaries (opex)
    _post(org, [("7100", D, "30000"), ("1100", C, "30000")])  # interest
    _post(org, [("7000", D, "20000"), ("1100", C, "20000")])  # tax


# ---------------------------------------------------------------------------
# Classification, not code prefixes
# ---------------------------------------------------------------------------


def test_control_accounts_are_classified(org: Organization) -> None:
    accounts = {a.code: a for a in Account.objects.filter(organization=org)}
    C = Account.Classification
    assert accounts["1500"].classification == C.CURRENT_ASSET  # inventory
    assert accounts["1700"].classification == C.NON_CURRENT_ASSET  # fixed assets
    assert accounts["2100"].classification == C.CURRENT_LIABILITY  # trade payables
    assert accounts["4100"].classification == C.REVENUE
    assert accounts["5000"].classification == C.COGS
    assert accounts["6100"].classification == C.OPERATING_EXPENSE
    assert accounts["7000"].classification == C.TAX_EXPENSE
    assert accounts["7100"].classification == C.FINANCE_COST


def test_a_new_5xxx_expense_does_not_silently_become_cost_of_sales(org: Organization) -> None:
    """The bug classification exists to prevent: the old report read any account
    whose code started with 5 as COGS, so this account wrecked gross margin."""
    marketing = Account.objects.create(
        organization=org,
        code="5500",
        name="Marketing",
        account_type=Account.Type.EXPENSE,
        classification=Account.Classification.OPERATING_EXPENSE,
        normal_balance=Account.Balance.DEBIT,
    )
    accounts = ensure_default_accounts(org)
    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    _post(org, [("1500", D, "600000"), ("2100", C, "600000")], when=PERIOD_START)
    _post(org, [("1100", D, "1000000"), ("4100", C, "1000000")])
    _post(org, [("5000", D, "600000"), ("1500", C, "600000")])
    post_journal(
        organization=org,
        entry_date=PERIOD_END,
        description="billboard",
        lines=[
            {"account": marketing, "side": D, "amount": Decimal("100000"), "memo": ""},
            {"account": accounts["1100"], "side": C, "amount": Decimal("100000"), "memo": ""},
        ],
    )

    pnl = profit_and_loss(org, start=PERIOD_START, end=PERIOD_END)
    # Cost of sales is 600k — the marketing spend sits in opex, below gross profit.
    assert pnl["cogs"] == Decimal("600000.00")
    assert pnl["gross_profit"] == Decimal("400000.00")
    assert pnl["gross_margin_pct"] == Decimal("40.00")
    assert pnl["operating_expenses"] == Decimal("100000.00")


# ---------------------------------------------------------------------------
# The P&L ladder
# ---------------------------------------------------------------------------


def test_profit_ladder_separates_operating_from_financing_and_tax(org: Organization) -> None:
    _trade(org)
    pnl = profit_and_loss(org, start=PERIOD_START, end=PERIOD_END)

    assert pnl["revenue"] == Decimal("1000000.00")
    assert pnl["cogs"] == Decimal("600000.00")
    assert pnl["gross_profit"] == Decimal("400000.00")
    assert pnl["operating_expenses"] == Decimal("200000.00")
    assert pnl["operating_profit"] == Decimal("200000.00")
    assert pnl["finance_cost"] == Decimal("30000.00")
    assert pnl["tax_expense"] == Decimal("20000.00")
    # Net profit is after interest and tax: 200k − 30k − 20k.
    assert pnl["net_profit"] == Decimal("150000.00")


def test_ebitda_adds_back_interest_and_tax_not_just_depreciation(org: Organization) -> None:
    """EBITDA = *earnings before interest, tax, depreciation and amortisation*.
    Computing it as net profit + depreciation (the old behaviour) understated it
    by exactly the interest and tax charged — here, by 50,000."""
    _trade(org)
    pnl = profit_and_loss(org, start=PERIOD_START, end=PERIOD_END)

    assert pnl["ebitda"] == Decimal("200000.00")
    assert pnl["ebitda"] == pnl["net_profit"] + pnl["finance_cost"] + pnl["tax_expense"]
    naive = pnl["net_profit"] + pnl["depreciation"]
    assert pnl["ebitda"] - naive == Decimal("50000.00")


# ---------------------------------------------------------------------------
# Balance sheet
# ---------------------------------------------------------------------------


def test_balance_sheet_groups_current_and_non_current_and_still_balances(
    org: Organization,
) -> None:
    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    _post(org, [("1100", D, "500000"), ("3000", C, "500000")])  # capital in
    _post(org, [("1700", D, "300000"), ("2100", C, "300000")])  # fixed asset on credit
    _trade(org)

    sheet = balance_sheet(org, as_of=PERIOD_END)
    assert sheet["balanced"] is True
    assert sheet["total_non_current_assets"] == Decimal("300000.00")
    assert sheet["total_current_assets"] == _q_sum(sheet["current_assets"])
    assert sheet["total_assets"] == (
        sheet["total_current_assets"] + sheet["total_non_current_assets"]
    )
    # Quick ratio excludes inventory; current ratio does not, so quick <= current.
    assert sheet["quick_ratio"] <= sheet["current_ratio"]


def _q_sum(lines: list[dict[str, Decimal]]) -> Decimal:
    return sum((line["amount"] for line in lines), Decimal("0.00"))


def test_trial_balance_still_balances_after_the_classification_change(
    org: Organization,
) -> None:
    _trade(org)
    tb = trial_balance(org, as_of=PERIOD_END)
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


# ---------------------------------------------------------------------------
# Cash conversion cycle
# ---------------------------------------------------------------------------


def test_cash_conversion_cycle_nets_the_three_components(org: Organization) -> None:
    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    _trade(org)
    _post(org, [("1400", D, "200000"), ("4100", C, "200000")])  # a credit sale

    cycle = working_capital_cycle(org, start=PERIOD_START, end=PERIOD_END)
    assert cycle["days"] == 30
    # DIO and DSO add days, DPO gives them back.
    assert cycle["cash_conversion_cycle_days"] == (
        cycle["dio_days"] + cycle["dso_days"] - cycle["dpo_days"]
    )
    assert cycle["dio_days"] > 0
    assert cycle["dso_days"] > 0


def test_a_negative_cycle_is_reported_as_supplier_funded(org: Organization) -> None:
    """Buy on long credit, sell for cash, hold little stock — suppliers fund the
    business and the cycle goes negative. That is a good thing and must not read
    as a funding requirement."""
    from apps.catalog.models import Supplier
    from apps.finance.models import SupplierBill

    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    # Buy a lot on credit, hold almost none of it, sell it all for cash: the
    # supplier is funding the business and the cycle should go negative.
    _post(org, [("1500", D, "900000"), ("2100", C, "900000")], when=PERIOD_START)
    _post(org, [("1100", D, "1000000"), ("4100", C, "1000000")])
    _post(org, [("5000", D, "880000"), ("1500", C, "880000")])

    # DPO is measured off the *bills* sub-ledger, not the 2100 control account —
    # the sub-ledger is what carries a due date, so it is the honest source.
    SupplierBill.objects.create(
        organization=org,
        supplier=Supplier.objects.create(name="Kigali Wholesale"),
        bill_number="INV-1",
        bill_date=PERIOD_START,
        due_date=PERIOD_END,
        total_amount=Decimal("900000"),
    )

    cycle = working_capital_cycle(org, start=PERIOD_START, end=PERIOD_END)
    assert cycle["dpo_days"] > cycle["dio_days"] + cycle["dso_days"]
    assert cycle["cash_conversion_cycle_days"] < 0
    assert cycle["working_capital_funding_need"] == Decimal("0.00")
    assert "supplier terms" in cycle["interpretation"].lower()


# ---------------------------------------------------------------------------
# Expiry exposure — the pharmacy-specific one
# ---------------------------------------------------------------------------


def _batch(org: Organization, product: Product, days_to_expiry: int, qty: int, cost: str) -> None:
    InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=f"B{days_to_expiry}-{qty}",
        expiry_date=date.today() + timedelta(days=days_to_expiry),
        quantity_available=qty,
        wholesale_cost=Decimal(cost),
    )


def test_expiry_exposure_bands_and_provisions_the_stock(org: Organization) -> None:
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    _batch(org, product, -5, 10, "1000")  # already expired  → 100% provision
    _batch(org, product, 20, 10, "1000")  # within 30 days   →  75%
    _batch(org, product, 50, 10, "1000")  # 31–60            →  50%
    _batch(org, product, 300, 100, "1000")  # healthy          →  no provision

    exposure = inventory_expiry_exposure(org)
    assert exposure["stock_value"] == Decimal("130000.00")
    # At-risk = the three short-dated batches, 10k each.
    assert exposure["at_risk_value"] == Decimal("30000.00")
    # Provision = 10k×1.00 + 10k×0.75 + 10k×0.50.
    assert exposure["suggested_provision"] == Decimal("22500.00")

    bands = {b["band"]: b for b in exposure["bands"]}
    assert bands["expired"]["cost_value"] == Decimal("10000.00")
    assert bands["expired"]["provision"] == Decimal("10000.00")
    assert bands["0_30"]["provision"] == Decimal("7500.00")
    assert bands["31_60"]["provision"] == Decimal("5000.00")
    assert bands["91_180"]["cost_value"] == Decimal("0.00")


def test_healthy_stock_produces_no_provision(org: Organization) -> None:
    product = Product.objects.create(generic_name="Paracetamol", strength="500mg")
    _batch(org, product, 400, 50, "500")
    exposure = inventory_expiry_exposure(org)
    assert exposure["at_risk_value"] == Decimal("0.00")
    assert exposure["suggested_provision"] == Decimal("0.00")
    assert exposure["stock_value"] == Decimal("25000.00")


# ---------------------------------------------------------------------------
# Break-even & returns
# ---------------------------------------------------------------------------


def test_break_even_and_margin_of_safety(org: Organization) -> None:
    _trade(org)
    result = break_even(org, start=PERIOD_START, end=PERIOD_END)
    # Fixed costs 200,000 at a 40% contribution margin → 500,000 of revenue.
    assert result["fixed_costs"] == Decimal("200000.00")
    assert result["contribution_margin_pct"] == Decimal("40.00")
    assert result["break_even_revenue"] == Decimal("500000.00")
    assert result["is_above_break_even"] is True
    # Revenue 1,000,000 against a 500,000 break-even → 50% headroom.
    assert result["margin_of_safety_pct"] == Decimal("50.00")


def test_returns_are_annualised_so_a_month_compares_to_a_year(org: Organization) -> None:
    D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT
    _post(org, [("1100", D, "2000000"), ("3000", C, "2000000")])
    _trade(org)

    returns = capital_returns(org, start=PERIOD_START, end=PERIOD_END)
    assert returns["annualised"] is True
    # A month's profit on the equity base, scaled to a year — so it is far above
    # the raw monthly percentage and comparable to an annual target.
    monthly_raw = returns["net_profit"] / returns["equity"] * 100
    assert returns["roe_pct"] > monthly_raw
    assert returns["roce_pct"] is not None


def test_gmroi_flags_stock_that_is_not_paying_for_itself(org: Organization) -> None:
    product = Product.objects.create(generic_name="Slow Mover", strength="10mg")
    # A large pile of stock against a small margin — GMROI below 1.
    _batch(org, product, 400, 10_000, "1000")
    _post(
        org,
        [("1100", JournalLine.Side.DEBIT, "100000"), ("4100", JournalLine.Side.CREDIT, "100000")],
    )
    _post(
        org,
        [("5000", JournalLine.Side.DEBIT, "90000"), ("1500", JournalLine.Side.CREDIT, "90000")],
    )

    returns = capital_returns(org, start=PERIOD_START, end=PERIOD_END)
    assert returns["gmroi"] is not None
    assert returns["gmroi"] < 1
    assert "not paying for itself" in (returns["gmroi_verdict"] or "")


def test_a_period_with_no_trading_reports_the_cycle_as_not_computable(
    org: Organization,
) -> None:
    """DIO/DSO/DPO are ratios; with no revenue and no cost of sales there is
    nothing to divide by. Printing "-7,227 days" from a negative denominator is
    worse than printing nothing, so the report says so instead."""
    cycle = working_capital_cycle(org, start=PERIOD_START, end=PERIOD_END)
    assert cycle["computable"] is False
    assert cycle["cash_conversion_cycle_days"] is None
    assert cycle["dio_days"] is None
    assert cycle["working_capital_funding_need"] == Decimal("0.00")
    assert "not enough trading" in cycle["interpretation"].lower()
