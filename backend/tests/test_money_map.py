"""Every way money moves must reach the ledger.

The coverage test is the structural one: it walks the money-map registry and
fails if a declared source has no importable posting path. A future feature that
moves money and forgets the books breaks the build rather than quietly
under-reporting costs for a year.

The rest assert the specific holes the redesign closed — card takings recorded as
cash, till shortages that never reached the P&L, assets that never depreciated,
and expiring stock still carried at full cost.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.models import Account, FixedAsset, JournalEntry, JournalLine
from apps.finance.moneymap import MONEY_SOURCES, coverage, summary
from apps.finance.operations import (
    current_provision_balance,
    monthly_charge,
    post_drawer_variance,
    post_expiry_provision,
    run_depreciation,
    settle_card_batch,
)
from apps.finance.reports import balance_sheet, profit_and_loss
from apps.finance.services import ensure_default_accounts, post_sale_journal
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch
from apps.retail.models import Payment, Sale, SaleItem

pytestmark = pytest.mark.django_db

START = date(2026, 6, 1)
END = date(2026, 6, 30)
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Remera Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


def _balances(org: Organization) -> dict[str, Decimal]:
    """Signed balance per account code, on the account's own normal side."""
    out: dict[str, Decimal] = {}
    for account in Account.objects.filter(organization=org):
        lines = JournalLine.objects.filter(account=account).exclude(
            entry__status=JournalEntry.Status.REVERSED
        )
        debit = sum((ln.amount for ln in lines if ln.side == D), Decimal("0"))
        credit = sum((ln.amount for ln in lines if ln.side == C), Decimal("0"))
        debit_side = account.normal_balance == Account.Balance.DEBIT
        signed = debit - credit if debit_side else credit - debit
        if signed:
            out[account.code] = signed
    return out


# --------------------------------------------------------------------------- #
# The registry itself
# --------------------------------------------------------------------------- #


def test_every_declared_money_source_has_a_wired_posting_path() -> None:
    """The structural guarantee: nothing in the map is a promise without an implementation."""
    unwired = [s.key for s in MONEY_SOURCES if not s.is_wired]
    assert unwired == [], f"Money sources with no importable posting path: {unwired}"


def test_the_map_covers_both_directions_and_names_its_treatment() -> None:
    rows = coverage()
    assert {r["direction"] for r in rows} == {"INFLOW", "OUTFLOW", "INTERNAL"}
    # A source without a stated GL treatment is a to-do pretending to be a design.
    assert all(r["treatment"] and r["reference_types"] for r in rows)


def test_summary_flags_a_wired_source_that_posted_nothing(org: Organization) -> None:
    result = summary(org, start=START, end=END)
    assert result["unwired"] == []
    assert "pos_sale" in result["idle"]  # nothing sold in an empty month


# --------------------------------------------------------------------------- #
# D9 — POS tenders
# --------------------------------------------------------------------------- #


def _sale_with_tenders(org: Organization, tenders: list[tuple[str, str]]) -> Sale:
    """A completed sale whose total is made up of the given tenders.

    `Sale.total` and `SaleItem.line_net` are computed properties, so the total is
    driven by the item's unit price rather than assigned.
    """
    product = Product.objects.create(generic_name="Paracetamol", strength="500mg")
    total = sum((Decimal(a) for _, a in tenders), Decimal("0"))
    sale = Sale.objects.create(organization=org, status="COMPLETED")
    SaleItem.objects.create(sale=sale, product=product, quantity=1, unit_price=total)
    for method, amount in tenders:
        Payment.objects.create(sale=sale, method=method, amount=Decimal(amount))
    return sale


def test_card_and_momo_takings_do_not_land_in_the_cash_drawer(org: Organization) -> None:
    """The defect: every tender used to debit 1100, so tills counted short by the card total."""
    sale = _sale_with_tenders(org, [("CASH", "4000"), ("MOBILE_MONEY", "3000"), ("CARD", "3000")])
    post_sale_journal(sale=sale, user=None)

    balances = _balances(org)
    assert balances["1100"] == Decimal("4000")  # only the cash actually in the drawer
    assert balances["1300"] == Decimal("3000")  # mobile money float
    assert balances["1150"] == Decimal("3000")  # card money, not yet settled
    assert balances["4100"] == Decimal("10000")


def test_a_sale_with_no_recorded_tender_still_posts_to_cash(org: Organization) -> None:
    """Older sales carry no Payment rows; the entry must still balance."""
    product = Product.objects.create(generic_name="Amoxicillin", strength="250mg")
    sale = Sale.objects.create(organization=org, status="COMPLETED")
    SaleItem.objects.create(sale=sale, product=product, quantity=1, unit_price=Decimal("5000"))
    entry = post_sale_journal(sale=sale, user=None)
    assert entry is not None
    assert _balances(org)["1100"] == Decimal("5000")


def test_card_settlement_clears_transit_and_expenses_the_fee(org: Organization) -> None:
    sale = _sale_with_tenders(org, [("CARD", "100000")])
    post_sale_journal(sale=sale, user=None)
    assert _balances(org)["1150"] == Decimal("100000")

    settle_card_batch(
        organization=org,
        gross=Decimal("100000"),
        fee=Decimal("2000"),
        settled_on=END,
        reference="ACQ-2026-06-30",
    )
    balances = _balances(org)
    assert "1150" not in balances  # transit cleared
    assert balances["1200"] == Decimal("98000")  # bank, net of the fee
    assert balances["6150"] == Decimal("2000")  # the fee is visible as a cost


def test_a_settlement_cannot_claim_a_fee_larger_than_the_takings(org: Organization) -> None:
    with pytest.raises(ValueError, match="between zero and the gross"):
        settle_card_batch(organization=org, gross=Decimal("1000"), fee=Decimal("1500"))


# --------------------------------------------------------------------------- #
# D9 — till variance
# --------------------------------------------------------------------------- #


class _Drawer:
    """A closed drawer session, minimal but shaped like the real model."""

    def __init__(self, organization: Organization, over_short: str) -> None:
        self.pk = 1
        self.organization = organization
        self.status = "CLOSED"
        self.over_short = Decimal(over_short)
        self.closed_at = None


def test_a_till_shortage_reaches_the_profit_and_loss(org: Organization) -> None:
    """It was computed and stored and never posted, so cash losses were invisible."""
    entry = post_drawer_variance(drawer=_Drawer(org, "-4500"), user=None)
    assert entry is not None
    balances = _balances(org)
    assert balances["6160"] == Decimal("4500")  # expense
    assert balances["1100"] == Decimal("-4500")  # cash reduced


def test_a_till_overage_posts_the_other_way(org: Organization) -> None:
    post_drawer_variance(drawer=_Drawer(org, "1200"), user=None)
    balances = _balances(org)
    assert balances["1100"] == Decimal("1200")
    assert balances["6160"] == Decimal("-1200")


def test_a_drawer_that_balanced_posts_nothing(org: Organization) -> None:
    assert post_drawer_variance(drawer=_Drawer(org, "0"), user=None) is None


# --------------------------------------------------------------------------- #
# D10 — depreciation
# --------------------------------------------------------------------------- #


def _asset(org: Organization, **kwargs: object) -> FixedAsset:
    defaults: dict[str, object] = {
        "organization": org,
        "asset_number": f"FA-{FixedAsset.objects.count() + 1:04d}",
        "name": "Vaccine fridge",
        "acquisition_date": date(2026, 1, 1),
        "acquisition_cost": Decimal("2400000"),
        "useful_life_years": 5,
        "salvage_value": Decimal("0"),
    }
    defaults.update(kwargs)
    return FixedAsset.objects.create(**defaults)  # type: ignore[arg-type]


def test_monthly_charge_is_straight_line_net_of_salvage(org: Organization) -> None:
    asset = _asset(org, acquisition_cost=Decimal("1200000"), salvage_value=Decimal("200000"))
    # (1,200,000 − 200,000) / 60 months
    assert monthly_charge(asset) == Decimal("16666.67")


def test_depreciation_posts_and_updates_the_register(org: Organization) -> None:
    asset = _asset(org)
    entry = run_depreciation(organization=org, as_of=END, user=None)
    assert entry is not None

    balances = _balances(org)
    assert balances["6500"] == Decimal("40000")  # 2,400,000 / 60
    assert balances["1701"] == Decimal("40000")  # accumulated depreciation
    asset.refresh_from_db()
    assert asset.accumulated_depreciation == Decimal("40000")


def test_running_depreciation_twice_in_a_month_does_not_double_charge(org: Organization) -> None:
    _asset(org)
    first = run_depreciation(organization=org, as_of=END, user=None)
    second = run_depreciation(organization=org, as_of=date(2026, 6, 15), user=None)
    assert first is not None and second is not None
    assert first.pk == second.pk
    assert _balances(org)["6500"] == Decimal("40000")


def test_an_asset_never_depreciates_below_its_salvage_value(org: Organization) -> None:
    asset = _asset(
        org,
        acquisition_cost=Decimal("120000"),
        salvage_value=Decimal("20000"),
        useful_life_years=1,
    )
    # Already 95,000 of the 100,000 depreciable amount written off.
    asset.accumulated_depreciation = Decimal("95000")
    asset.save(update_fields=["accumulated_depreciation"])

    run_depreciation(organization=org, as_of=END, user=None)
    asset.refresh_from_db()
    assert asset.accumulated_depreciation == Decimal("100000")
    assert _balances(org)["6500"] == Decimal("5000")  # capped, not the full 8,333.33


def test_depreciation_makes_ebitda_differ_from_operating_profit(org: Organization) -> None:
    """The add-back was always zero because no account was classified DEPRECIATION."""
    _asset(org)
    run_depreciation(organization=org, as_of=END, user=None)

    pnl = profit_and_loss(org, start=START, end=END)
    assert pnl["depreciation"] == Decimal("40000.00")
    assert pnl["ebitda"] - pnl["operating_profit"] == Decimal("40000.00")


# --------------------------------------------------------------------------- #
# D6 — expiry provision
# --------------------------------------------------------------------------- #


def _expiring_batch(org: Organization, *, days: int, cost: str, qty: int = 100) -> InventoryBatch:
    n = InventoryBatch.objects.count() + 1
    product = Product.objects.create(generic_name=f"Drug {n}", strength="10mg")
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=f"B{n}",
        quantity_available=qty,
        expiry_date=END + timedelta(days=days),
        wholesale_cost=Decimal(cost),
    )


def test_the_provision_reaches_the_balance_sheet_not_just_a_dashboard(org: Organization) -> None:
    """IAS 2: stock that will not sell before it expires is not worth its cost."""
    _expiring_batch(org, days=15, cost="500")  # 50,000 at cost, in the 0–30 day band

    entry = post_expiry_provision(organization=org, as_of=END, user=None)
    assert entry is not None

    balances = _balances(org)
    assert balances["1590"] > 0  # contra-asset carried
    assert balances["5900"] > 0  # charge taken to the P&L
    assert balances["1590"] == balances["5900"]

    # And the statements now reflect it.
    bs = balance_sheet(org, as_of=END)
    assert any(line["code"] == "1590" for line in bs["current_assets"])


def test_only_the_movement_is_posted_not_the_whole_provision_again(org: Organization) -> None:
    """Re-recognising the full provision monthly would churn the P&L with offsetting entries."""
    _expiring_batch(org, days=15, cost="500")
    post_expiry_provision(organization=org, as_of=END, user=None)
    first = current_provision_balance(org)
    assert first > 0

    # Same stock, next month: nothing has changed, so nothing should post.
    assert post_expiry_provision(organization=org, as_of=END, user=None) is None
    assert current_provision_balance(org) == first


def test_a_provision_no_longer_needed_is_released(org: Organization) -> None:
    batch = _expiring_batch(org, days=15, cost="500")
    post_expiry_provision(organization=org, as_of=END, user=None)
    carried = current_provision_balance(org)
    assert carried > 0

    # The stock sold before it expired.
    batch.quantity_available = 0
    batch.save(update_fields=["quantity_available"])

    entry = post_expiry_provision(organization=org, as_of=date(2026, 7, 31), user=None)
    assert entry is not None
    assert current_provision_balance(org) == Decimal("0.00")
