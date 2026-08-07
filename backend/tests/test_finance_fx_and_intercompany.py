"""FX revaluation (IAS 21) and unrealised profit on intercompany stock.

The two items the finance redesign left explicitly open. Both are about value
that moves without a transaction: a currency drifting under an open balance, and
a margin that only looks like profit until you consolidate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.fx import FxError, exposure_report, rate_for, revalue, seed_rate
from apps.finance.models import Account, ExchangeRate, JournalEntry, JournalLine
from apps.finance.reports import intercompany_eliminations, unrealised_profit_in_stock
from apps.finance.services import ensure_default_accounts, post_journal
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch

pytestmark = pytest.mark.django_db

JUNE = date(2026, 6, 30)
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Kigali Importers", type="DEPOT")
    ensure_default_accounts(organization)
    return organization


def _post_fc(org: Organization, code: str, side: str, fc: str, rate: str, when: date) -> None:
    """A posting struck in USD, carried in the ledger at the rate on the day."""
    accounts = ensure_default_accounts(org)
    base = (Decimal(fc) * Decimal(rate)).quantize(Decimal("0.01"))
    other = accounts["1500"] if code != "1500" else accounts["1100"]
    post_journal(
        organization=org,
        entry_date=when,
        description="Import",
        lines=[
            {
                "account": accounts[code],
                "side": side,
                "amount": base,
                "memo": "",
                "currency": "USD",
                "amount_fc": Decimal(fc),
                "exchange_rate": Decimal(rate),
            },
            {
                "account": other,
                "side": C if side == D else D,
                "amount": base,
                "memo": "",
            },
        ],
    )


# --------------------------------------------------------------------------- #
# Rates
# --------------------------------------------------------------------------- #


def test_the_rate_in_force_is_the_latest_published_on_or_before_the_date() -> None:
    """Falling forward would restate a period with news that did not exist yet."""
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=date(2026, 6, 30), rate_to_base=Decimal("1350"))

    assert rate_for("USD", on=date(2026, 6, 15)) == Decimal("1300.000000")
    assert rate_for("USD", on=date(2026, 6, 30)) == Decimal("1350.000000")
    assert rate_for("USD", on=date(2026, 7, 10)) == Decimal("1350.000000")


def test_the_base_currency_never_needs_a_rate() -> None:
    assert rate_for("RWF", on=JUNE) == Decimal("1")


def test_a_missing_rate_is_refused_rather_than_guessed(org: Organization) -> None:
    with pytest.raises(FxError, match="No exchange rate published"):
        rate_for("EUR", on=JUNE)


def test_rates_are_effective_dated_not_overwritten() -> None:
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=date(2026, 6, 30), rate_to_base=Decimal("1350"))
    assert ExchangeRate.objects.filter(currency="USD").count() == 2


# --------------------------------------------------------------------------- #
# Revaluation
# --------------------------------------------------------------------------- #


def test_a_payable_is_restated_when_the_currency_moves_against_you(org: Organization) -> None:
    """Owe USD 10,000 at 1,300; the rate goes to 1,350; you owe 500,000 more.

    No transaction created that cost — the currency moved while the balance sat
    open — so nothing in the ledger notices it without this.
    """
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=JUNE, rate_to_base=Decimal("1350"))
    _post_fc(org, "2100", C, "10000", "1300", date(2026, 6, 1))

    report = exposure_report(org, as_of=JUNE)
    exposure = report["exposures"][0]
    assert exposure["currency"] == "USD"
    assert exposure["carrying_amount"] == "-13000000.00"  # a payable, credit balance
    assert exposure["restated_amount"] == "-13500000.00"
    assert exposure["difference"] == "-500000.00"
    assert report["net_unrealised"] == "-500000.00"

    revaluation = revalue(organization=org, as_of=JUNE)
    assert revaluation is not None
    assert revaluation.net_gain == Decimal("-500000.00")

    entry = revaluation.journal_entry
    assert entry is not None
    fx_line = entry.lines.get(account__code="7100")
    assert fx_line.side == D  # a loss
    assert fx_line.amount == Decimal("500000.00")


def test_a_receivable_gains_when_the_currency_moves_your_way(org: Organization) -> None:
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=JUNE, rate_to_base=Decimal("1350"))
    _post_fc(org, "1400", D, "10000", "1300", date(2026, 6, 1))

    revaluation = revalue(organization=org, as_of=JUNE)
    assert revaluation is not None
    assert revaluation.net_gain == Decimal("500000.00")
    assert revaluation.journal_entry.lines.get(account__code="7100").side == C


def test_inventory_is_not_revalued(org: Organization) -> None:
    """Non-monetary under IAS 21: stock stays at what it cost on arrival.

    Revaluing it would restate the cost of goods that are simply sitting on a shelf.
    """
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=JUNE, rate_to_base=Decimal("1350"))
    _post_fc(org, "1500", D, "10000", "1300", date(2026, 6, 1))

    assert Account.objects.get(organization=org, code="1500").is_monetary is False
    assert exposure_report(org, as_of=JUNE)["exposures"] == []
    assert revalue(organization=org, as_of=JUNE) is None


def test_revaluing_twice_does_not_post_twice(org: Organization) -> None:
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    seed_rate(currency="USD", rate_date=JUNE, rate_to_base=Decimal("1350"))
    _post_fc(org, "2100", C, "10000", "1300", date(2026, 6, 1))

    first = revalue(organization=org, as_of=JUNE)
    second = revalue(organization=org, as_of=JUNE)
    assert first is not None and second is not None and first.pk == second.pk
    assert JournalEntry.objects.filter(reference_type="fx_revaluation").count() == 1


def test_a_rate_that_has_not_moved_posts_nothing(org: Organization) -> None:
    seed_rate(currency="USD", rate_date=date(2026, 6, 1), rate_to_base=Decimal("1300"))
    _post_fc(org, "2100", C, "10000", "1300", date(2026, 6, 1))
    assert revalue(organization=org, as_of=JUNE) is None


def test_the_exposure_report_says_so_when_it_cannot_compute(org: Organization) -> None:
    _post_fc(org, "2100", C, "5000", "1300", date(2026, 6, 1))
    ExchangeRate.objects.all().delete()

    report = exposure_report(org, as_of=JUNE)
    assert report["computable"] is False
    assert "No exchange rate published" in report["interpretation"]


# --------------------------------------------------------------------------- #
# Unrealised profit on intercompany stock
# --------------------------------------------------------------------------- #


@pytest.fixture
def group(db: None) -> tuple[Organization, Organization]:
    depot = Organization.objects.create(name="Group Depot", type="DEPOT")
    branch = Organization.objects.create(name="Group Branch", type="RETAIL")
    ensure_default_accounts(depot)
    ensure_default_accounts(branch)
    return depot, branch


def _transferred_batch(
    *, to: Organization, frm: Organization, qty: int, transfer_price: str, origin: str | None
) -> InventoryBatch:
    product = Product.objects.create(
        generic_name=f"Drug {InventoryBatch.objects.count() + 1}", strength="10mg"
    )
    return InventoryBatch.objects.create(
        organization=to,
        source_org=frm,
        product=product,
        batch_number=f"B{InventoryBatch.objects.count() + 1}",
        quantity_available=qty,
        expiry_date=date(2027, 1, 1),
        wholesale_cost=Decimal(transfer_price),
        origin_unit_cost=Decimal(origin) if origin is not None else None,
    )


def test_margin_on_stock_still_inside_the_group_is_not_group_profit(
    group: tuple[Organization, Organization],
) -> None:
    """The depot marked it up; until it leaves the group that is one pocket
    paying another."""
    depot, branch = group
    _transferred_batch(to=branch, frm=depot, qty=100, transfer_price="1200", origin="1000")

    result = unrealised_profit_in_stock([depot, branch], as_of=JUNE)
    assert result["unrealised_profit"] == Decimal("20000.00")  # 200 margin × 100
    assert result["batches"] == 1
    assert result["unmeasured_batches"] == 0
    assert result["note"] == ""


def test_stock_bought_from_outside_the_group_carries_no_elimination(
    group: tuple[Organization, Organization],
) -> None:
    depot, branch = group
    outsider = Organization.objects.create(name="Independent Wholesaler", type="DEPOT")
    _transferred_batch(to=branch, frm=outsider, qty=100, transfer_price="1200", origin="1000")

    assert unrealised_profit_in_stock([depot, branch], as_of=JUNE)["unrealised_profit"] == Decimal(
        "0.00"
    )


def test_a_batch_with_no_origin_cost_is_reported_not_assumed(
    group: tuple[Organization, Organization],
) -> None:
    """Assuming zero margin would understate the adjustment and nobody would know."""
    depot, branch = group
    _transferred_batch(to=branch, frm=depot, qty=50, transfer_price="1200", origin=None)

    result = unrealised_profit_in_stock([depot, branch], as_of=JUNE)
    assert result["unrealised_profit"] == Decimal("0.00")
    assert result["unmeasured_batches"] == 1
    assert "not eliminated" in result["note"]
    assert "floor, not the" in result["note"]


def test_stock_sold_on_leaves_nothing_to_eliminate(
    group: tuple[Organization, Organization],
) -> None:
    """Once it is outside the group the margin is genuinely earned."""
    depot, branch = group
    batch = _transferred_batch(to=branch, frm=depot, qty=100, transfer_price="1200", origin="1000")
    batch.quantity_available = 0
    batch.save(update_fields=["quantity_available"])

    assert unrealised_profit_in_stock([depot, branch], as_of=JUNE)["unrealised_profit"] == Decimal(
        "0.00"
    )


def test_the_elimination_feeds_consolidated_profit(
    group: tuple[Organization, Organization],
) -> None:
    depot, branch = group
    _transferred_batch(to=branch, frm=depot, qty=100, transfer_price="1200", origin="1000")

    eliminations = intercompany_eliminations([depot, branch], start=date(2026, 6, 1), end=JUNE)
    assert eliminations["profit_effect"] == Decimal("20000.00")
    assert eliminations["unrealised_profit"] == "20000.00"


def test_a_single_entity_has_no_intercompany_stock(org: Organization) -> None:
    assert unrealised_profit_in_stock([org], as_of=JUNE)["unrealised_profit"] == Decimal("0.00")
