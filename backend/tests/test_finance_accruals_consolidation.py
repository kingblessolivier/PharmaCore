"""Accruals, prepayments, and consolidation that nets off internal trade.

Two things a monthly P&L needs to be honest about:

* a cost belongs to the months it was incurred in, not the month it was billed;
* a group has not earned anything until it sells to someone outside itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.finance.accruals import (
    ScheduleError,
    amount_for_period,
    cancel_schedule,
    create_schedule,
    post_period,
    run_schedules,
    schedule_summary,
)
from apps.finance.models import (
    Account,
    CustomerInvoice,
    JournalEntry,
    JournalLine,
    RecurringSchedule,
)
from apps.finance.reports import consolidated, intercompany_eliminations, profit_and_loss
from apps.finance.services import ensure_default_accounts, post_journal
from apps.iam.models import Organization

pytestmark = pytest.mark.django_db

D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Nyabugogo Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


def _balances(org: Organization) -> dict[str, Decimal]:
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
# Prepayments
# --------------------------------------------------------------------------- #


def test_an_annual_premium_is_released_month_by_month(org: Organization) -> None:
    """Insurance paid in January belongs to all twelve months, not to January."""
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Annual stock insurance",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("1200000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    post_period(schedule=schedule, period_month=date(2026, 1, 1))

    balances = _balances(org)
    assert balances["6120"] == Decimal("100000")  # one month charged
    assert balances["1600"] == Decimal("-100000")  # prepayment drawn down

    january = profit_and_loss(org, start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert january["operating_expenses"] == Decimal("100000.00")


def test_a_prepayment_never_reverses(org: Organization) -> None:
    """The asset really is consumed; reversing it would un-charge the month."""
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Rent paid in advance",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6110"],
        total_amount=Decimal("600000"),
        periods=6,
        start_month=date(2026, 1, 1),
        auto_reverse=True,  # asked for, but ignored for a prepayment
    )
    assert schedule.auto_reverse is False
    run = post_period(schedule=schedule, period_month=date(2026, 1, 1))
    assert run is not None and run.reversal_entry is None


def test_the_last_month_absorbs_the_rounding_remainder(org: Organization) -> None:
    """Otherwise a stub balance is left that nobody can ever clear."""
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Awkward total",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("1000000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    months = [date(2026, m, 1) for m in range(1, 13)]
    assert amount_for_period(schedule, months[0]) == Decimal("83333.33")
    assert amount_for_period(schedule, months[-1]) == Decimal("83333.37")

    for month in months:
        post_period(schedule=schedule, period_month=month)
    # The prepayment account is fully released — no residue.
    assert _balances(org).get("1600", Decimal("0")) == Decimal("-1000000")


# --------------------------------------------------------------------------- #
# Accruals
# --------------------------------------------------------------------------- #


def test_an_accrual_reverses_so_the_invoice_is_not_counted_twice(org: Organization) -> None:
    """The charge goes in at month end and comes straight back out on the 1st.

    When the supplier's invoice arrives it is posted normally, and the cost lands
    once.
    """
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Q1 electricity, not yet billed",
        kind=RecurringSchedule.Kind.ACCRUAL,
        expense_account=accounts["6130"],
        total_amount=Decimal("300000"),
        periods=3,
        start_month=date(2026, 1, 1),
    )
    assert schedule.auto_reverse is True

    run = post_period(schedule=schedule, period_month=date(2026, 1, 1))
    assert run is not None and run.reversal_entry is not None
    assert run.journal_entry is not None
    assert run.journal_entry.entry_date == date(2026, 1, 31)
    assert run.reversal_entry.entry_date == date(2026, 2, 1)

    # January carries the cost.
    january = profit_and_loss(org, start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert january["operating_expenses"] == Decimal("100000.00")

    # Across both months the accrual nets to nil, leaving room for the real invoice.
    both = profit_and_loss(org, start=date(2026, 1, 1), end=date(2026, 2, 28))
    assert both["operating_expenses"] == Decimal("0.00")
    assert _balances(org).get("2170", Decimal("0")) == Decimal("0")


def test_an_accrual_lands_in_the_accruals_liability(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Audit fee accrual",
        kind=RecurringSchedule.Kind.ACCRUAL,
        expense_account=accounts["6130"],
        total_amount=Decimal("240000"),
        periods=12,
        start_month=date(2026, 1, 1),
        auto_reverse=False,
    )
    post_period(schedule=schedule, period_month=date(2026, 1, 1))
    assert _balances(org)["2170"] == Decimal("20000")


# --------------------------------------------------------------------------- #
# Running them
# --------------------------------------------------------------------------- #


def test_a_month_is_never_charged_twice(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Licence fee",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("120000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    first = post_period(schedule=schedule, period_month=date(2026, 1, 1))
    second = post_period(schedule=schedule, period_month=date(2026, 1, 1))
    assert first is not None and second is not None
    assert first.pk == second.pk
    assert schedule.runs.count() == 1
    assert _balances(org)["6120"] == Decimal("10000")


def test_running_late_catches_up_month_by_month(org: Organization) -> None:
    """Three missed months post to the months they belong to, not all to today."""
    accounts = ensure_default_accounts(org)
    create_schedule(
        organization=org,
        name="Backdated insurance",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("360000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    result = run_schedules(organization=org, as_of=date(2026, 3, 15))
    assert result["runs"] == 3

    dates = sorted(
        e.entry_date for e in JournalEntry.objects.filter(reference_type="recurring_schedule")
    )
    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]

    # And re-running the same month adds nothing.
    assert run_schedules(organization=org, as_of=date(2026, 3, 15))["runs"] == 0


def test_a_schedule_completes_when_every_month_is_posted(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Short spread",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("30000"),
        periods=3,
        start_month=date(2026, 1, 1),
    )
    run_schedules(organization=org, as_of=date(2026, 3, 31))
    schedule.refresh_from_db()
    assert schedule.status == RecurringSchedule.Status.COMPLETED
    assert schedule.remaining == Decimal("0.00")


def test_cancelling_requires_a_reason_and_stops_future_charges(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    schedule = create_schedule(
        organization=org,
        name="Cancelled cover",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("120000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    post_period(schedule=schedule, period_month=date(2026, 1, 1))

    with pytest.raises(ScheduleError, match="requires a reason"):
        cancel_schedule(schedule=schedule, reason="")

    cancel_schedule(schedule=schedule, reason="Policy cancelled mid-term.")
    assert post_period(schedule=schedule, period_month=date(2026, 2, 1)) is None
    # What was already charged stays charged.
    assert _balances(org)["6120"] == Decimal("10000")


def test_summary_reports_what_is_still_sitting_on_the_balance_sheet(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    create_schedule(
        organization=org,
        name="Insurance",
        kind=RecurringSchedule.Kind.PREPAYMENT,
        expense_account=accounts["6120"],
        total_amount=Decimal("120000"),
        periods=12,
        start_month=date(2026, 1, 1),
    )
    run_schedules(organization=org, as_of=date(2026, 2, 28))

    summary = schedule_summary(org, as_of=date(2026, 2, 28))
    assert summary["prepayments_remaining"] == "100000.00"
    assert summary["overdue"] == []


def test_a_schedule_needs_a_positive_total_and_at_least_one_month(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    common = {
        "organization": org,
        "name": "Bad",
        "kind": RecurringSchedule.Kind.PREPAYMENT,
        "expense_account": accounts["6120"],
        "start_month": date(2026, 1, 1),
    }
    with pytest.raises(ScheduleError, match="at least one month"):
        create_schedule(total_amount=Decimal("100"), periods=0, **common)  # type: ignore[arg-type]
    with pytest.raises(ScheduleError, match="positive total"):
        create_schedule(total_amount=Decimal("0"), periods=3, **common)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Consolidation
# --------------------------------------------------------------------------- #


@pytest.fixture
def group(db: None) -> tuple[Organization, Organization]:
    depot = Organization.objects.create(name="Group Depot", type="DEPOT")
    branch = Organization.objects.create(name="Group Retail", type="RETAIL")
    ensure_default_accounts(depot)
    ensure_default_accounts(branch)
    return depot, branch


def _sell(org: Organization, amount: str, when: date) -> None:
    accounts = ensure_default_accounts(org)
    value = Decimal(amount)
    post_journal(
        organization=org,
        entry_date=when,
        description="Sale",
        lines=[
            {"account": accounts["1400"], "side": D, "amount": value, "memo": ""},
            {"account": accounts["4200"], "side": C, "amount": value, "memo": ""},
        ],
    )


def test_a_depots_sale_to_its_own_branch_is_not_group_revenue(
    group: tuple[Organization, Organization],
) -> None:
    """Summing branches counts the same goods twice on their way through one business."""
    depot, branch = group
    start, end = date(2026, 6, 1), date(2026, 6, 30)

    _sell(depot, "1000000", date(2026, 6, 10))  # to its own branch
    _sell(branch, "1400000", date(2026, 6, 20))  # on to the public

    CustomerInvoice.objects.create(
        organization=depot,
        customer=branch,
        invoice_number="INV-IC-1",
        invoice_date=date(2026, 6, 10),
        due_date=date(2026, 7, 10),
        total_amount=Decimal("1000000"),
        vat_amount=Decimal("0"),
    )

    result = consolidated([depot, branch], start=start, end=end)
    assert result["gross_totals"]["revenue"] == Decimal("2400000.00")
    assert result["eliminations"]["revenue"] == Decimal("1000000.00")
    # Only the sale to someone outside the group survives.
    assert result["totals"]["revenue"] == Decimal("1400000.00")
    assert result["eliminations"]["invoice_count"] == 1


def test_a_sale_to_a_real_customer_is_never_eliminated(
    group: tuple[Organization, Organization],
) -> None:
    depot, branch = group
    outsider = Organization.objects.create(name="Independent Pharmacy", type="RETAIL")
    CustomerInvoice.objects.create(
        organization=depot,
        customer=outsider,
        invoice_number="INV-EXT-1",
        invoice_date=date(2026, 6, 12),
        due_date=date(2026, 7, 12),
        total_amount=Decimal("800000"),
        vat_amount=Decimal("0"),
    )
    eliminations = intercompany_eliminations(
        [depot, branch], start=date(2026, 6, 1), end=date(2026, 6, 30)
    )
    assert eliminations["revenue"] == Decimal("0.00")
    assert eliminations["invoice_count"] == 0


def test_vat_on_an_internal_invoice_is_stripped_before_eliminating(
    group: tuple[Organization, Organization],
) -> None:
    """The buyer recovers it, so it never was group income."""
    depot, branch = group
    CustomerInvoice.objects.create(
        organization=depot,
        customer=branch,
        invoice_number="INV-IC-VAT",
        invoice_date=date(2026, 6, 10),
        due_date=date(2026, 7, 10),
        total_amount=Decimal("1180000"),
        vat_amount=Decimal("180000"),
    )
    eliminations = intercompany_eliminations(
        [depot, branch], start=date(2026, 6, 1), end=date(2026, 6, 30)
    )
    assert eliminations["revenue"] == Decimal("1000000.00")


def test_intercompany_trade_with_no_stock_left_inside_the_group_needs_no_profit_adjustment(
    group: tuple[Organization, Organization],
) -> None:
    """Goods sold on outside the group have genuinely earned their margin.

    This test previously asserted a *limitation* note, because unrealised profit
    could not be measured at all. It now asserts the behaviour, since
    `InventoryBatch.origin_unit_cost` closed that gap — see the F6 entry in
    docs/development/documentation-and-closeout-plan.md.
    """
    depot, branch = group
    CustomerInvoice.objects.create(
        organization=depot,
        customer=branch,
        invoice_number="INV-IC-2",
        invoice_date=date(2026, 6, 10),
        due_date=date(2026, 7, 10),
        total_amount=Decimal("500000"),
        vat_amount=Decimal("0"),
    )
    eliminations = intercompany_eliminations(
        [depot, branch], start=date(2026, 6, 1), end=date(2026, 6, 30)
    )
    assert eliminations["revenue"] == Decimal("500000.00")
    # Nothing transferred is still on the shelf, so no margin is trapped inside.
    assert eliminations["profit_effect"] == Decimal("0.00")
    assert eliminations["unrealised_profit_note"] == ""


def test_a_single_entity_has_nothing_to_eliminate(org: Organization) -> None:
    eliminations = intercompany_eliminations([org], start=date(2026, 6, 1), end=date(2026, 6, 30))
    assert eliminations["revenue"] == Decimal("0.00")
    assert eliminations["unrealised_profit_note"] == ""
