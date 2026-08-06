"""Finance reporting: trial balance, P&L, balance sheet, and the performance
metrics the leader reads at a glance.

ROADMAP "9. Finance" — *"the owner/finance-head must know: how much is invested,
how the business is performing (gross & net profit + margins), who owes us and how
old, and is cash safe."* Everything here is derived from posted journal entries;
nothing is stored twice. A report is a query over the ledger, never a second source
of truth that could drift from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, Q, Sum, When
from django.db.models.functions import Coalesce

from apps.finance.models import Account, JournalEntry, JournalLine, SupplierBill
from apps.iam.models import Organization

_MONEY: DecimalField = DecimalField(max_digits=16, decimal_places=2)
ZERO = Decimal("0.00")


def _q(value: Decimal | int | float | None) -> Decimal:
    """Coerce to 2-dp Decimal money."""
    return (Decimal(str(value or 0))).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class AccountBalance:
    code: str
    name: str
    account_type: str
    normal_balance: str
    debit: Decimal
    credit: Decimal

    @property
    def signed(self) -> Decimal:
        """Balance signed so the account's own normal side reads positive."""
        if self.normal_balance == Account.Balance.DEBIT:
            return self.debit - self.credit
        return self.credit - self.debit


def account_balances(
    organization: Organization,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[AccountBalance]:
    """Per-account debit/credit turnover over an optional date window.

    Omit ``start`` for an inception-to-date balance (what a balance sheet needs);
    pass both for period activity (what a P&L needs).
    """
    entry_filter = Q(lines__entry__organization=organization)
    entry_filter &= ~Q(lines__entry__status=JournalEntry.Status.REVERSED)
    if start is not None:
        entry_filter &= Q(lines__entry__entry_date__gte=start)
    if end is not None:
        entry_filter &= Q(lines__entry__entry_date__lte=end)

    rows = (
        Account.objects.filter(organization=organization)
        .annotate(
            debit=Coalesce(
                Sum(
                    Case(
                        When(
                            entry_filter & Q(lines__side=JournalLine.Side.DEBIT),
                            then="lines__amount",
                        ),
                        output_field=_MONEY,
                    )
                ),
                0,
                output_field=_MONEY,
            ),
            credit=Coalesce(
                Sum(
                    Case(
                        When(
                            entry_filter & Q(lines__side=JournalLine.Side.CREDIT),
                            then="lines__amount",
                        ),
                        output_field=_MONEY,
                    )
                ),
                0,
                output_field=_MONEY,
            ),
        )
        .order_by("code")
    )
    return [
        AccountBalance(
            code=a.code,
            name=a.name,
            account_type=a.account_type,
            normal_balance=a.normal_balance,
            debit=_q(a.debit),
            credit=_q(a.credit),
        )
        for a in rows
    ]


def trial_balance(organization: Organization, *, as_of: date | None = None) -> dict[str, Any]:
    """Every account's debit/credit totals with the grand totals that must agree.

    In double-entry the two columns are equal by construction; a mismatch means
    something wrote to the ledger without going through post_journal(), so the
    report reports it rather than hiding it.
    """
    balances = account_balances(organization, end=as_of)
    rows = [b for b in balances if b.debit or b.credit]
    total_debit = sum((b.debit for b in rows), ZERO)
    total_credit = sum((b.credit for b in rows), ZERO)
    return {
        "as_of": as_of,
        "rows": [
            {
                "code": b.code,
                "name": b.name,
                "account_type": b.account_type,
                "debit": b.debit,
                "credit": b.credit,
            }
            for b in rows
        ],
        "total_debit": _q(total_debit),
        "total_credit": _q(total_credit),
        "balanced": _q(total_debit) == _q(total_credit),
    }


def profit_and_loss(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Revenue → COGS → gross profit → operating expenses → net profit, for a period.

    Margins follow the standard definitions the ROADMAP asks for:
      gross margin % = gross profit / revenue
      net margin %   = net profit / revenue
    EBITDA here = net profit + depreciation (interest/tax lines are modelled as
    ordinary expense accounts until the tax module books them separately).
    """
    balances = account_balances(organization, start=start, end=end)

    revenue = sum((b.signed for b in balances if b.account_type == Account.Type.REVENUE), ZERO)
    cogs = sum((b.signed for b in balances if b.code.startswith("5")), ZERO)
    all_expense = sum((b.signed for b in balances if b.account_type == Account.Type.EXPENSE), ZERO)
    opex = all_expense - cogs
    depreciation = sum((b.signed for b in balances if b.code.startswith("65")), ZERO)

    gross_profit = revenue - cogs
    net_profit = revenue - all_expense

    def pct(numerator: Decimal) -> Decimal:
        return _q(numerator / revenue * 100) if revenue else ZERO

    return {
        "start": start,
        "end": end,
        "revenue": _q(revenue),
        "cogs": _q(cogs),
        "gross_profit": _q(gross_profit),
        "gross_margin_pct": pct(gross_profit),
        "operating_expenses": _q(opex),
        "net_profit": _q(net_profit),
        "net_margin_pct": pct(net_profit),
        "ebitda": _q(net_profit + depreciation),
        "expense_lines": [
            {"code": b.code, "name": b.name, "amount": _q(b.signed)}
            for b in balances
            if b.account_type == Account.Type.EXPENSE and b.signed
        ],
        "revenue_lines": [
            {"code": b.code, "name": b.name, "amount": _q(b.signed)}
            for b in balances
            if b.account_type == Account.Type.REVENUE and b.signed
        ],
    }


def balance_sheet(organization: Organization, *, as_of: date | None = None) -> dict[str, Any]:
    """Assets = Liabilities + Equity, where equity carries the retained earnings
    the P&L has produced inception-to-date.

    Revenue and expense accounts are *not* separate sections of a balance sheet —
    their net rolls into retained earnings. That roll-up is what makes the sheet
    balance, so it is computed here rather than assumed.
    """
    balances = account_balances(organization, end=as_of)

    assets = sum((b.signed for b in balances if b.account_type == Account.Type.ASSET), ZERO)
    liabilities = sum(
        (b.signed for b in balances if b.account_type == Account.Type.LIABILITY), ZERO
    )
    contributed_equity = sum(
        (b.signed for b in balances if b.account_type == Account.Type.EQUITY), ZERO
    )
    revenue = sum((b.signed for b in balances if b.account_type == Account.Type.REVENUE), ZERO)
    expenses = sum((b.signed for b in balances if b.account_type == Account.Type.EXPENSE), ZERO)
    retained_earnings = revenue - expenses
    total_equity = contributed_equity + retained_earnings

    def section(kind: str) -> list[dict[str, Any]]:
        return [
            {"code": b.code, "name": b.name, "amount": _q(b.signed)}
            for b in balances
            if b.account_type == kind and b.signed
        ]

    return {
        "as_of": as_of,
        "assets": section(Account.Type.ASSET),
        "liabilities": section(Account.Type.LIABILITY),
        "equity": section(Account.Type.EQUITY),
        "total_assets": _q(assets),
        "total_liabilities": _q(liabilities),
        "contributed_equity": _q(contributed_equity),
        "retained_earnings": _q(retained_earnings),
        "total_equity": _q(total_equity),
        "balanced": _q(assets) == _q(liabilities + total_equity),
    }


def _receivable_and_payable(organization: Organization, as_of: date) -> tuple[Decimal, Decimal]:
    """Outstanding AR (from the ledger's control account) and AP (from open bills)."""
    balances = {b.code: b for b in account_balances(organization, end=as_of)}
    ar = balances["1100"].signed if "1100" in balances else ZERO
    payable = sum(
        (
            b.amount_due
            for b in SupplierBill.objects.filter(organization=organization).exclude(
                status=SupplierBill.Status.PAID
            )
        ),
        ZERO,
    )
    return _q(ar), _q(payable)


def performance(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """The performance cockpit: this period's P&L headlines, the same figures for
    the preceding period of equal length, and the working-capital ratios.

    DSO/DPO use the standard formulas over the period actually requested:
      DSO = receivables / revenue * days
      DPO = payables / COGS * days
    """
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    current = profit_and_loss(organization, start=start, end=end)
    previous = profit_and_loss(organization, start=prev_start, end=prev_end)
    receivable, payable = _receivable_and_payable(organization, end)

    dso = _q(receivable / current["revenue"] * days) if current["revenue"] else ZERO
    dpo = _q(payable / current["cogs"] * days) if current["cogs"] else ZERO

    def delta_pct(now: Decimal, before: Decimal) -> Decimal | None:
        """Percentage change vs the previous period; None when there is no base to
        compare against (an infinite jump from zero is not a meaningful percentage)."""
        if not before:
            return None
        return _q((now - before) / abs(before) * 100)

    return {
        "start": start,
        "end": end,
        "days": days,
        "previous_start": prev_start,
        "previous_end": prev_end,
        "revenue": current["revenue"],
        "cogs": current["cogs"],
        "gross_profit": current["gross_profit"],
        "gross_margin_pct": current["gross_margin_pct"],
        "operating_expenses": current["operating_expenses"],
        "net_profit": current["net_profit"],
        "net_margin_pct": current["net_margin_pct"],
        "ebitda": current["ebitda"],
        "receivable": receivable,
        "payable": payable,
        "dso_days": dso,
        "dpo_days": dpo,
        "previous": {
            "revenue": previous["revenue"],
            "cogs": previous["cogs"],
            "gross_profit": previous["gross_profit"],
            "net_profit": previous["net_profit"],
        },
        "delta_pct": {
            "revenue": delta_pct(current["revenue"], previous["revenue"]),
            "gross_profit": delta_pct(current["gross_profit"], previous["gross_profit"]),
            "net_profit": delta_pct(current["net_profit"], previous["net_profit"]),
        },
    }


def cash_flow_statement(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Direct-method cash-flow: every movement through a cash account in the period,
    classified by what the *other* side of the entry hit.

    Operating — trading counterparties (revenue, expenses, AR, AP, statutory payables).
    Investing — fixed assets (the 15xx block).
    Financing — equity and borrowings.

    Classifying by the contra-account is what makes this a real statement rather
    than a relabelled bank list: the same 10,000 leaving the bank is an operating
    outflow if it paid a supplier and a financing outflow if it repaid the owner.
    """
    cash_codes = set(
        Account.objects.filter(
            Q(organization=organization),
            Q(code="1000") | Q(code__startswith="1000-"),
        ).values_list("code", flat=True)
    )

    buckets = {"operating": ZERO, "investing": ZERO, "financing": ZERO}
    movements: dict[str, list[dict[str, Any]]] = {"operating": [], "investing": [], "financing": []}

    entries = (
        JournalEntry.objects.filter(
            organization=organization, entry_date__gte=start, entry_date__lte=end
        )
        .exclude(status=JournalEntry.Status.REVERSED)
        .prefetch_related("lines__account")
    )

    for entry in entries:
        lines = list(entry.lines.all())
        cash_lines = [ln for ln in lines if ln.account.code in cash_codes]
        if not cash_lines:
            continue
        other_lines = [ln for ln in lines if ln.account.code not in cash_codes]

        net_cash = sum(
            (ln.amount if ln.side == JournalLine.Side.DEBIT else -ln.amount for ln in cash_lines),
            ZERO,
        )
        if not net_cash:
            continue

        contra = other_lines[0].account if other_lines else cash_lines[0].account
        if contra.code.startswith("15"):
            kind = "investing"
        elif contra.account_type == Account.Type.EQUITY or contra.code.startswith("27"):
            kind = "financing"
        else:
            kind = "operating"

        buckets[kind] += net_cash
        movements[kind].append(
            {
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date,
                "description": entry.description,
                "amount": _q(net_cash),
            }
        )

    prior = account_balances(organization, end=start - timedelta(days=1))
    opening = sum((b.signed for b in prior if b.code in cash_codes), ZERO)

    net_change = buckets["operating"] + buckets["investing"] + buckets["financing"]
    return {
        "start": start,
        "end": end,
        "operating": _q(buckets["operating"]),
        "investing": _q(buckets["investing"]),
        "financing": _q(buckets["financing"]),
        "net_change": _q(net_change),
        "opening_cash": _q(opening),
        "closing_cash": _q(opening + net_change),
        "movements": movements,
    }


def consolidated(organizations: list[Organization], *, start: date, end: date) -> dict[str, Any]:
    """HQ consolidation: the group's P&L and balance sheet, plus each branch's
    contribution so a head office can see who is carrying the group.

    Branches are summed, not averaged — and each branch's own figures stay visible
    beside the total, because a group number that hides a loss-making branch is
    exactly what consolidation is supposed to expose.
    """
    per_branch: list[dict[str, Any]] = []
    totals = {
        "revenue": ZERO,
        "cogs": ZERO,
        "gross_profit": ZERO,
        "operating_expenses": ZERO,
        "net_profit": ZERO,
        "total_assets": ZERO,
        "total_liabilities": ZERO,
        "total_equity": ZERO,
    }

    for org in organizations:
        pl = profit_and_loss(org, start=start, end=end)
        bs = balance_sheet(org, as_of=end)
        row = {
            "organization": org.pk,
            "organization_name": org.name,
            "revenue": pl["revenue"],
            "cogs": pl["cogs"],
            "gross_profit": pl["gross_profit"],
            "gross_margin_pct": pl["gross_margin_pct"],
            "operating_expenses": pl["operating_expenses"],
            "net_profit": pl["net_profit"],
            "net_margin_pct": pl["net_margin_pct"],
            "total_assets": bs["total_assets"],
            "total_liabilities": bs["total_liabilities"],
            "total_equity": bs["total_equity"],
        }
        per_branch.append(row)
        for key in totals:
            totals[key] += row[key]

    group_revenue = totals["revenue"]
    return {
        "start": start,
        "end": end,
        "branches": per_branch,
        "totals": {k: _q(v) for k, v in totals.items()},
        "group_gross_margin_pct": (
            _q(totals["gross_profit"] / group_revenue * 100) if group_revenue else ZERO
        ),
        "group_net_margin_pct": (
            _q(totals["net_profit"] / group_revenue * 100) if group_revenue else ZERO
        ),
    }


def revenue_vs_cogs_series(
    organization: Organization, *, start: date, end: date
) -> list[dict[str, Any]]:
    """Monthly revenue and COGS across the window — the cockpit's trend chart.

    Two measures of similar scale, returned as one series set so the UI can draw
    them on a single axis (docs/design/09 forbids dual-axis charts).
    """
    points: list[dict[str, Any]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = date(cursor.year + (cursor.month // 12), (cursor.month % 12) + 1, 1)
        window_end = min(next_month - timedelta(days=1), end)
        pl = profit_and_loss(organization, start=max(cursor, start), end=window_end)
        points.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "revenue": pl["revenue"],
                "cogs": pl["cogs"],
                "gross_profit": pl["gross_profit"],
            }
        )
        cursor = next_month
    return points
