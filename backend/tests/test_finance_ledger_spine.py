"""The ledger spine: cost centres, budgets read from the books, and the close checklist.

These assert the things the previous design could not do at all. The important one
is `test_budget_actuals_come_from_the_ledger_not_a_column`: the old model let you
type the actual in beside the budget, so a variance report proved nothing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.finance.budgeting import budget_variance, cost_centre_pnl, months_between
from apps.finance.closing import (
    CloseBlocked,
    assert_period_closable,
    close_readiness,
    seed_period_tasks,
    settle_task,
)
from apps.finance.models import (
    AccountingPeriod,
    Budget,
    BudgetLine,
    CostCentre,
    JournalEntry,
    JournalLine,
    PeriodTask,
)
from apps.finance.services import close_period, ensure_default_accounts, post_journal
from apps.iam.models import Organization

pytestmark = pytest.mark.django_db

JAN = date(2026, 1, 1)
MAR_END = date(2026, 3, 31)
DEC_END = date(2026, 12, 31)

D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Kacyiru Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


@pytest.fixture
def centres(org: Organization) -> dict[str, CostCentre]:
    retail = CostCentre.objects.create(
        organization=org, code="RETAIL", name="Retail", kind=CostCentre.Kind.FUNCTION
    )
    return {
        "retail": retail,
        "kacyiru": CostCentre.objects.create(
            organization=org, code="KAC", name="Kacyiru", kind=CostCentre.Kind.BRANCH, parent=retail
        ),
        "remera": CostCentre.objects.create(
            organization=org, code="REM", name="Remera", kind=CostCentre.Kind.BRANCH, parent=retail
        ),
    }


def _post(
    org: Organization,
    lines: list[tuple[str, str, str]],
    *,
    when: date = MAR_END,
    centre: CostCentre | None = None,
    source: str = JournalEntry.Source.MANUAL,
) -> JournalEntry:
    accounts = ensure_default_accounts(org)
    return post_journal(
        organization=org,
        entry_date=when,
        description="test",
        source_module=source,
        cost_centre=centre,
        lines=[
            {"account": accounts[code], "side": side, "amount": Decimal(amount), "memo": ""}
            for code, side, amount in lines
        ],
    )


# --------------------------------------------------------------------------- #
# Cost centres
# --------------------------------------------------------------------------- #


def test_a_centre_rolls_up_through_its_parents(centres: dict[str, CostCentre]) -> None:
    assert centres["kacyiru"].path == "Retail / Kacyiru"
    assert set(centres["retail"].descendant_ids()) == {
        centres["retail"].pk,
        centres["kacyiru"].pk,
        centres["remera"].pk,
    }
    # A leaf is its own only descendant.
    assert centres["kacyiru"].descendant_ids() == [centres["kacyiru"].pk]


def test_a_posting_carries_its_cost_centre(
    org: Organization, centres: dict[str, CostCentre]
) -> None:
    entry = _post(org, [("6110", D, "300000"), ("1100", C, "300000")], centre=centres["kacyiru"])
    assert {ln.cost_centre_id for ln in entry.lines.all()} == {centres["kacyiru"].pk}
    assert entry.source_module == JournalEntry.Source.MANUAL


def test_a_line_may_override_the_entry_wide_centre(
    org: Organization, centres: dict[str, CostCentre]
) -> None:
    """One rent invoice, split across two branches — the reason lines carry centres."""
    accounts = ensure_default_accounts(org)
    entry = post_journal(
        organization=org,
        entry_date=MAR_END,
        description="Rent split",
        cost_centre=centres["kacyiru"],
        lines=[
            {"account": accounts["6110"], "side": D, "amount": Decimal("200000"), "memo": ""},
            {
                "account": accounts["6110"],
                "side": D,
                "amount": Decimal("100000"),
                "memo": "",
                "cost_centre": centres["remera"],
            },
            {"account": accounts["1100"], "side": C, "amount": Decimal("300000"), "memo": ""},
        ],
    )
    by_centre = {(ln.cost_centre.code, ln.amount) for ln in entry.lines.filter(side=D)}
    assert by_centre == {("KAC", Decimal("200000.00")), ("REM", Decimal("100000.00"))}


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #


def test_months_between_is_inclusive_at_both_ends() -> None:
    assert months_between(JAN, MAR_END) == [(2026, 1), (2026, 2), (2026, 3)]
    assert months_between(date(2026, 12, 1), date(2027, 1, 31)) == [(2026, 12), (2027, 1)]
    assert months_between(MAR_END, JAN) == []


def test_budget_actuals_come_from_the_ledger_not_a_column(
    org: Organization, centres: dict[str, CostCentre]
) -> None:
    """The defect this whole model change exists to fix.

    Nothing anywhere lets a caller supply an actual. The only way a number reaches
    the `actual` column of a variance report is by being posted to the ledger.
    """
    assert not hasattr(BudgetLine, "actual_amount")

    accounts = ensure_default_accounts(org)
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    BudgetLine.objects.create(
        budget=budget,
        account=accounts["6110"],
        cost_centre=centres["kacyiru"],
        period_month=3,
        amount=Decimal("500000"),
    )
    _post(org, [("6110", D, "620000"), ("1100", C, "620000")], centre=centres["kacyiru"])

    result = budget_variance(budget, start=JAN, end=MAR_END)
    row = next(r for r in result["rows"] if r["code"] == "6110")
    assert row["budget"] == "500000.00"
    assert row["actual"] == "620000.00"
    assert row["variance"] == "-120000.00"
    # Overspending an expense is adverse.
    assert row["verdict"] == "ADVERSE"


def test_variance_direction_is_read_the_right_way_round_per_account(org: Organization) -> None:
    """Under-spending an expense is good news; under-selling revenue is not.

    A naive `budget - actual` reports both as the same positive number.
    """
    accounts = ensure_default_accounts(org)
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    BudgetLine.objects.create(
        budget=budget, account=accounts["4100"], period_month=3, amount=Decimal("1000000")
    )
    BudgetLine.objects.create(
        budget=budget, account=accounts["6110"], period_month=3, amount=Decimal("500000")
    )
    # Sold less than planned, spent less than planned.
    _post(org, [("1100", D, "800000"), ("4100", C, "800000")])
    _post(org, [("6110", D, "400000"), ("1100", C, "400000")])

    rows = {r["code"]: r for r in budget_variance(budget, start=JAN, end=MAR_END)["rows"]}
    assert rows["4100"]["variance"] == "200000.00"
    assert rows["4100"]["verdict"] == "ADVERSE"  # under plan on revenue
    assert rows["6110"]["variance"] == "100000.00"
    assert rows["6110"]["verdict"] == "FAVOURABLE"  # under plan on cost


def test_an_annual_budget_line_is_prorated_across_a_partial_window(org: Organization) -> None:
    """A yearly figure asked about one quarter contributes a quarter of itself."""
    accounts = ensure_default_accounts(org)
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    BudgetLine.objects.create(
        budget=budget, account=accounts["6110"], period_month=None, amount=Decimal("1200000")
    )

    quarter = budget_variance(budget, start=JAN, end=MAR_END)
    assert quarter["total_budget"] == "300000.00"  # 3/12
    full_year = budget_variance(budget, start=JAN, end=DEC_END)
    assert full_year["total_budget"] == "1200000.00"


def test_spend_with_no_budget_still_appears(org: Organization) -> None:
    """The most useful row in a variance report, and the old design could not produce it."""
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    _post(org, [("6120", D, "75000"), ("1100", C, "75000")])

    result = budget_variance(budget, start=JAN, end=MAR_END)
    unbudgeted = {r["code"] for r in result["unbudgeted_rows"]}
    assert "6120" in unbudgeted
    assert next(r for r in result["rows"] if r["code"] == "6120")["budget"] == "0.00"


def test_variance_can_be_narrowed_to_one_branch(
    org: Organization, centres: dict[str, CostCentre]
) -> None:
    accounts = ensure_default_accounts(org)
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    BudgetLine.objects.create(
        budget=budget,
        account=accounts["6110"],
        cost_centre=centres["kacyiru"],
        period_month=3,
        amount=Decimal("500000"),
    )
    _post(org, [("6110", D, "400000"), ("1100", C, "400000")], centre=centres["kacyiru"])
    _post(org, [("6110", D, "900000"), ("1100", C, "900000")], centre=centres["remera"])

    only_kacyiru = budget_variance(budget, start=JAN, end=MAR_END, cost_centre=centres["kacyiru"])
    assert only_kacyiru["total_actual"] == "400000.00"
    # The parent rolls both branches up.
    both = budget_variance(budget, start=JAN, end=MAR_END, cost_centre=centres["retail"])
    assert both["total_actual"] == "1300000.00"


def test_reversed_entries_are_excluded_from_actuals(org: Organization) -> None:
    """A variance report and a P&L must never disagree about what was spent."""
    budget = Budget.objects.create(organization=org, name="FY2026", financial_year=2026)
    entry = _post(org, [("6110", D, "250000"), ("1100", C, "250000")])
    entry.status = JournalEntry.Status.REVERSED
    entry.save(update_fields=["status"])

    assert budget_variance(budget, start=JAN, end=MAR_END)["total_actual"] == "0.00"


# --------------------------------------------------------------------------- #
# Cost-centre P&L
# --------------------------------------------------------------------------- #


def test_cost_centre_pnl_reports_contribution_and_how_much_is_tagged(
    org: Organization, centres: dict[str, CostCentre]
) -> None:
    _post(org, [("1100", D, "1000000"), ("4100", C, "1000000")], centre=centres["kacyiru"])
    _post(org, [("5000", D, "600000"), ("1500", C, "600000")], centre=centres["kacyiru"])
    _post(org, [("6110", D, "150000"), ("1100", C, "150000")], centre=centres["kacyiru"])
    # Untagged revenue — head office, or simply not coded yet.
    _post(org, [("1100", D, "250000"), ("4100", C, "250000")])

    result = cost_centre_pnl(org, start=JAN, end=MAR_END)
    kacyiru = next(r for r in result["rows"] if r["code"] == "KAC")
    assert kacyiru["revenue"] == "1000000.00"
    assert kacyiru["gross_profit"] == "400000.00"
    assert kacyiru["contribution"] == "250000.00"

    # Untagged postings are reported as their own row, never spread across the
    # others — allocation is a policy decision, not something to invent here.
    unallocated = next(r for r in result["rows"] if r["name"] == "Unallocated")
    assert unallocated["revenue"] == "250000.00"
    assert result["tagged_pct"] == "80.00"


# --------------------------------------------------------------------------- #
# Period close
# --------------------------------------------------------------------------- #


def _period(org: Organization) -> AccountingPeriod:
    return AccountingPeriod.objects.create(
        organization=org,
        kind=AccountingPeriod.Kind.MONTH,
        start_date=JAN,
        end_date=date(2026, 1, 31),
    )


def test_seeding_the_checklist_is_idempotent(org: Organization) -> None:
    period = _period(org)
    first = seed_period_tasks(period)
    assert len(first) > 0
    assert seed_period_tasks(period) == []
    assert period.tasks.count() == len(first)


def test_a_blocking_task_stops_the_close(org: Organization) -> None:
    period = _period(org)
    seed_period_tasks(period)
    with pytest.raises(CloseBlocked, match="blocked by outstanding checklist items"):
        assert_period_closable(period)

    # close_period surfaces it as a plain refusal rather than a 500.
    with pytest.raises(ValueError, match="blocked by outstanding checklist items"):
        close_period(
            organization=org,
            kind=AccountingPeriod.Kind.MONTH,
            start_date=JAN,
            end_date=date(2026, 1, 31),
            user=None,
        )


def test_settling_every_blocking_task_clears_the_close(org: Organization) -> None:
    period = _period(org)
    seed_period_tasks(period)
    for task in period.tasks.filter(is_blocking=True):
        settle_task(task, status=PeriodTask.Status.DONE, user=None)

    readiness = close_readiness(period)
    assert readiness["is_ready"] is True
    assert readiness["blocking"] == []
    assert_period_closable(period)  # does not raise

    # The advisory task is still outstanding, and that is allowed.
    assert readiness["outstanding"] >= 1


def test_waiving_a_task_requires_a_reason(org: Organization) -> None:
    """A waiver without a reason is indistinguishable from skipping it."""
    period = _period(org)
    seed_period_tasks(period)
    task = period.tasks.first()
    assert task is not None

    with pytest.raises(ValueError, match="requires a reason"):
        settle_task(task, status=PeriodTask.Status.WAIVED, user=None, notes="   ")

    settle_task(task, status=PeriodTask.Status.WAIVED, user=None, notes="No stock movement in Jan.")
    task.refresh_from_db()
    assert task.status == PeriodTask.Status.WAIVED
    assert task.notes == "No stock movement in Jan."


def test_a_period_with_no_checklist_still_closes(org: Organization) -> None:
    """The checklist is a control added later; it must not retro-block old closes."""
    period = _period(org)
    assert period.tasks.count() == 0
    assert_period_closable(period)  # does not raise
