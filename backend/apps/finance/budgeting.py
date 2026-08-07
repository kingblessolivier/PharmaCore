"""Budget variance, with actuals read from the general ledger.

The old model stored ``actual_amount`` as an editable column next to the budget it
was supposed to test. Nothing computed it. A variance report whose actual figure is
typed in by the person being measured is not a control, so the column is gone and
every actual in this module comes from posted journal lines.

Two pieces of domain care that a naive ``budget - actual`` gets wrong:

* **Direction.** Under-spending an expense is favourable; under-selling revenue is
  not. Variance is reported as a signed number *and* a verdict, and the verdict
  depends on which way the account is supposed to go.
* **Annual lines.** A line with no ``period_month`` is a figure for the whole year.
  Asked about one quarter it contributes a quarter of itself — not all of it, which
  would make every partial period look catastrophic, and not nothing, which would
  make it look free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Case, DecimalField, Q, Sum, When
from django.db.models.functions import Coalesce

from apps.iam.models import Organization

from .models import Account, Budget, BudgetLine, CostCentre, JournalEntry, JournalLine

ZERO = Decimal("0.00")
_MONEY: DecimalField = DecimalField(max_digits=18, decimal_places=2)

# Classifications where spending *more* than planned is the bad outcome. Revenue
# and other income are the mirror image.
_COST_KINDS = {
    "COGS",
    "OPERATING_EXPENSE",
    "DEPRECIATION",
    "FINANCE_COST",
    "TAX_EXPENSE",
}
_INCOME_KINDS = {"REVENUE", "OTHER_INCOME"}


def _q(value: Decimal | int | float | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def months_between(start: date, end: date) -> list[tuple[int, int]]:
    """Every (year, month) the window touches, inclusive at both ends."""
    if end < start:
        return []
    out: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        out.append((year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


@dataclass
class VarianceRow:
    account_id: int
    code: str
    name: str
    classification: str
    cost_centre_id: int | None
    cost_centre: str
    budget: Decimal
    actual: Decimal

    @property
    def variance(self) -> Decimal:
        """Budget less actual — positive means the actual came in under plan."""
        return _q(self.budget - self.actual)

    @property
    def variance_pct(self) -> Decimal | None:
        if self.budget == 0:
            return None
        return _q(self.variance / self.budget * 100)

    @property
    def verdict(self) -> str:
        """FAVOURABLE / ADVERSE / ON_PLAN, read the right way round per account."""
        if self.variance == 0:
            return "ON_PLAN"
        under_plan = self.variance > 0
        if self.classification in _INCOME_KINDS:
            # Under plan on revenue is bad.
            return "ADVERSE" if under_plan else "FAVOURABLE"
        if self.classification in _COST_KINDS:
            return "FAVOURABLE" if under_plan else "ADVERSE"
        return "ON_PLAN"

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "code": self.code,
            "name": self.name,
            "classification": self.classification,
            "cost_centre_id": self.cost_centre_id,
            "cost_centre": self.cost_centre,
            "budget": str(self.budget),
            "actual": str(self.actual),
            "variance": str(self.variance),
            "variance_pct": None if self.variance_pct is None else str(self.variance_pct),
            "verdict": self.verdict,
        }


def budgeted_amounts(
    budget: Budget,
    *,
    start: date,
    end: date,
    cost_centre: CostCentre | None = None,
) -> dict[tuple[int, int | None], Decimal]:
    """Planned spend per (account, cost centre) for the window.

    Monthly lines count only if their month falls inside the window. Annual lines
    are pro-rated by how many of the year's twelve months the window covers.
    """
    wanted_months = {m for _, m in months_between(start, end)}
    if not wanted_months:
        return {}
    annual_share = Decimal(len(wanted_months)) / Decimal(12)

    lines = BudgetLine.objects.filter(budget=budget).select_related("account", "cost_centre")
    if cost_centre is not None:
        lines = lines.filter(cost_centre_id__in=cost_centre.descendant_ids())

    totals: dict[tuple[int, int | None], Decimal] = {}
    for line in lines:
        if line.period_month is None:
            amount = line.amount * annual_share
        elif line.period_month in wanted_months:
            amount = line.amount
        else:
            continue
        key = (line.account_id, line.cost_centre_id)
        totals[key] = totals.get(key, ZERO) + amount
    return {k: _q(v) for k, v in totals.items()}


def actual_amounts(
    organization: Organization,
    *,
    start: date,
    end: date,
    account_ids: list[int] | None = None,
    cost_centre: CostCentre | None = None,
) -> dict[tuple[int, int | None], Decimal]:
    """Posted activity per (account, cost centre), signed by normal balance.

    Reversed entries are excluded, exactly as the statements exclude them, so a
    variance report and a P&L can never disagree about what was spent.
    """
    lines = JournalLine.objects.filter(
        entry__organization=organization,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
    ).exclude(entry__status=JournalEntry.Status.REVERSED)

    if account_ids is not None:
        lines = lines.filter(account_id__in=account_ids)
    if cost_centre is not None:
        lines = lines.filter(cost_centre_id__in=cost_centre.descendant_ids())

    rows = (
        lines.values("account_id", "cost_centre_id", "account__normal_balance")
        .annotate(
            debit=Coalesce(
                Sum(Case(When(side=JournalLine.Side.DEBIT, then="amount"), output_field=_MONEY)),
                0,
                output_field=_MONEY,
            ),
            credit=Coalesce(
                Sum(Case(When(side=JournalLine.Side.CREDIT, then="amount"), output_field=_MONEY)),
                0,
                output_field=_MONEY,
            ),
        )
        .order_by()
    )

    out: dict[tuple[int, int | None], Decimal] = {}
    for row in rows:
        debit, credit = _q(row["debit"]), _q(row["credit"])
        signed = (
            debit - credit
            if row["account__normal_balance"] == Account.Balance.DEBIT
            else credit - debit
        )
        out[(row["account_id"], row["cost_centre_id"])] = signed
    return out


def budget_variance(
    budget: Budget,
    *,
    start: date,
    end: date,
    cost_centre: CostCentre | None = None,
) -> dict[str, Any]:
    """Budget vs actual for one plan over one window.

    Rows appear for anything that was budgeted *or* spent — an account with real
    spend and no budget is the single most useful row in a variance report, and
    the old design could not produce it.
    """
    organization = budget.organization
    planned = budgeted_amounts(budget, start=start, end=end, cost_centre=cost_centre)
    budgeted_account_ids = {a for a, _ in planned}

    # Restrict actuals to P&L accounts: a budget is about performance, and pulling
    # in balance-sheet movement would drown the report in cash and AP noise.
    pl_accounts = {
        a.id: a
        for a in Account.objects.filter(organization=organization).filter(
            Q(classification__in=_COST_KINDS | _INCOME_KINDS) | Q(id__in=budgeted_account_ids)
        )
    }
    actual = actual_amounts(
        organization,
        start=start,
        end=end,
        account_ids=list(pl_accounts),
        cost_centre=cost_centre,
    )

    centre_names = {c.id: c.name for c in CostCentre.objects.filter(organization=organization)}

    rows: list[VarianceRow] = []
    for key in sorted(set(planned) | set(actual), key=lambda k: (k[0], k[1] or 0)):
        account_id, centre_id = key
        account = pl_accounts.get(account_id)
        if account is None:
            continue
        rows.append(
            VarianceRow(
                account_id=account_id,
                code=account.code,
                name=account.name,
                classification=account.classification or "OPERATING_EXPENSE",
                cost_centre_id=centre_id,
                cost_centre=(
                    centre_names.get(centre_id, "Unallocated") if centre_id else "Unallocated"
                ),
                budget=planned.get(key, ZERO),
                actual=actual.get(key, ZERO),
            )
        )

    total_budget = _q(sum((r.budget for r in rows), ZERO))
    total_actual = _q(sum((r.actual for r in rows), ZERO))
    return {
        "budget_id": budget.id,
        "budget": budget.name,
        "financial_year": budget.financial_year,
        "status": budget.status,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "cost_centre_id": cost_centre.id if cost_centre else None,
        "cost_centre": cost_centre.name if cost_centre else None,
        "months_covered": len(months_between(start, end)),
        "total_budget": str(total_budget),
        "total_actual": str(total_actual),
        "total_variance": str(_q(total_budget - total_actual)),
        "rows": [r.as_dict() for r in rows],
        "unbudgeted_rows": [r.as_dict() for r in rows if r.budget == 0 and r.actual != 0],
    }


@dataclass
class CentreResult:
    centre_id: int | None
    code: str
    name: str
    revenue: Decimal = ZERO
    cost_of_sales: Decimal = ZERO
    operating_expenses: Decimal = ZERO
    lines: list[dict[str, Any]] = field(default_factory=list)

    @property
    def gross_profit(self) -> Decimal:
        return _q(self.revenue - self.cost_of_sales)

    @property
    def contribution(self) -> Decimal:
        return _q(self.gross_profit - self.operating_expenses)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cost_centre_id": self.centre_id,
            "code": self.code,
            "name": self.name,
            "revenue": str(_q(self.revenue)),
            "cost_of_sales": str(_q(self.cost_of_sales)),
            "gross_profit": str(self.gross_profit),
            "operating_expenses": str(_q(self.operating_expenses)),
            "contribution": str(self.contribution),
        }


def cost_centre_pnl(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """A P&L broken out by cost centre — the question the ledger could not answer.

    Postings with no centre are reported as "Unallocated" rather than spread across
    the others. Allocation is a policy decision, and inventing one here would hide
    how much of the business is untagged.
    """
    centres = {c.id: c for c in CostCentre.objects.filter(organization=organization)}
    accounts = {
        a.id: a
        for a in Account.objects.filter(organization=organization).filter(
            classification__in=_COST_KINDS | _INCOME_KINDS
        )
    }
    actual = actual_amounts(organization, start=start, end=end, account_ids=list(accounts))

    results: dict[int | None, CentreResult] = {}
    for (account_id, centre_id), amount in actual.items():
        account = accounts.get(account_id)
        if account is None:
            continue
        result = results.get(centre_id)
        if result is None:
            centre = centres.get(centre_id) if centre_id else None
            result = CentreResult(
                centre_id=centre_id,
                code=centre.code if centre else "—",
                name=centre.name if centre else "Unallocated",
            )
            results[centre_id] = result

        classification = account.classification or "OPERATING_EXPENSE"
        if classification in _INCOME_KINDS:
            result.revenue += amount
        elif classification == "COGS":
            result.cost_of_sales += amount
        else:
            result.operating_expenses += amount

    rows = sorted(results.values(), key=lambda r: (r.centre_id is None, r.code))
    allocated = _q(sum((abs(r.revenue) for r in rows if r.centre_id), ZERO))
    unallocated = _q(sum((abs(r.revenue) for r in rows if not r.centre_id), ZERO))
    total = allocated + unallocated
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": [r.as_dict() for r in rows],
        "total_revenue": str(_q(sum((r.revenue for r in rows), ZERO))),
        "total_contribution": str(_q(sum((r.contribution for r in rows), ZERO))),
        # How much of the P&L is actually tagged — the honest measure of whether
        # this report can be trusted yet.
        "tagged_pct": str(_q(allocated / total * 100)) if total else "0.00",
    }
