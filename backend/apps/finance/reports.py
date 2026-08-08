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

from django.db.models import Case, DecimalField, F, Q, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.finance.models import Account, JournalEntry, JournalLine, SupplierBill
from apps.finance.services import default_classification
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
    classification: str
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
            classification=a.classification or default_classification(a.account_type),
            normal_balance=a.normal_balance,
            debit=_q(a.debit),
            credit=_q(a.credit),
        )
        for a in rows
    ]


def _by_classification(balances: list[AccountBalance], *kinds: str) -> Decimal:
    """Signed total of every account rolling into the given statement lines."""
    wanted = set(kinds)
    return sum((b.signed for b in balances if b.classification in wanted), ZERO)


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
    C = Account.Classification
    balances = account_balances(organization, start=start, end=end)

    revenue = _by_classification(balances, C.REVENUE)
    other_income = _by_classification(balances, C.OTHER_INCOME)
    cogs = _by_classification(balances, C.COGS)
    opex = _by_classification(balances, C.OPERATING_EXPENSE)
    depreciation = _by_classification(balances, C.DEPRECIATION)
    finance_cost = _by_classification(balances, C.FINANCE_COST)
    tax_expense = _by_classification(balances, C.TAX_EXPENSE)

    gross_profit = revenue - cogs
    # Operating profit is before interest and tax; EBITDA adds depreciation back
    # on top of that. Computing EBITDA as "net profit + depreciation" (which is
    # what this did) understates it by exactly the interest and tax charged.
    operating_profit = gross_profit + other_income - opex - depreciation
    ebitda = operating_profit + depreciation
    net_profit = operating_profit - finance_cost - tax_expense

    def pct(numerator: Decimal) -> Decimal:
        return _q(numerator / revenue * 100) if revenue else ZERO

    def lines(*kinds: str) -> list[dict[str, Any]]:
        wanted = set(kinds)
        return [
            {
                "code": b.code,
                "name": b.name,
                "classification": b.classification,
                "amount": _q(b.signed),
            }
            for b in balances
            if b.classification in wanted and b.signed
        ]

    return {
        "start": start,
        "end": end,
        "revenue": _q(revenue),
        "other_income": _q(other_income),
        "cogs": _q(cogs),
        "gross_profit": _q(gross_profit),
        "gross_margin_pct": pct(gross_profit),
        "operating_expenses": _q(opex),
        "depreciation": _q(depreciation),
        "operating_profit": _q(operating_profit),
        "operating_margin_pct": pct(operating_profit),
        "finance_cost": _q(finance_cost),
        "tax_expense": _q(tax_expense),
        "net_profit": _q(net_profit),
        "net_margin_pct": pct(net_profit),
        "ebitda": _q(ebitda),
        "ebitda_margin_pct": pct(ebitda),
        "revenue_lines": lines(C.REVENUE, C.OTHER_INCOME),
        "cogs_lines": lines(C.COGS),
        "expense_lines": lines(C.OPERATING_EXPENSE, C.DEPRECIATION, C.FINANCE_COST, C.TAX_EXPENSE),
    }


def balance_sheet(organization: Organization, *, as_of: date | None = None) -> dict[str, Any]:
    """Assets = Liabilities + Equity, where equity carries the retained earnings
    the P&L has produced inception-to-date.

    Revenue and expense accounts are *not* separate sections of a balance sheet —
    their net rolls into retained earnings. That roll-up is what makes the sheet
    balance, so it is computed here rather than assumed.
    """
    C = Account.Classification
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

    current_assets = _by_classification(balances, C.CURRENT_ASSET)
    non_current_assets = _by_classification(balances, C.NON_CURRENT_ASSET)
    current_liabilities = _by_classification(balances, C.CURRENT_LIABILITY)
    non_current_liabilities = _by_classification(balances, C.NON_CURRENT_LIABILITY)

    def section(*kinds: str) -> list[dict[str, Any]]:
        wanted = set(kinds)
        return [
            {
                "code": b.code,
                "name": b.name,
                "classification": b.classification,
                "amount": _q(b.signed),
            }
            for b in balances
            if b.classification in wanted and b.signed
        ]

    # Inventory is the pharmacy's biggest and least liquid current asset, so the
    # quick ratio (which excludes it) is the honest solvency read — a pharmacy can
    # look comfortable on the current ratio and still not be able to pay a supplier.
    inventory = sum((b.signed for b in balances if b.code == "1500"), ZERO)
    quick_assets = current_assets - inventory

    def ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
        return _q(numerator / denominator) if denominator else None

    return {
        "as_of": as_of,
        # Grouped sections — a balance sheet is read current-vs-non-current, not
        # as one flat list of accounts.
        "current_assets": section(C.CURRENT_ASSET),
        "non_current_assets": section(C.NON_CURRENT_ASSET),
        "current_liabilities": section(C.CURRENT_LIABILITY),
        "non_current_liabilities": section(C.NON_CURRENT_LIABILITY),
        "equity": section(C.EQUITY),
        # Flat sections kept for callers that predate the grouping.
        "assets": section(C.CURRENT_ASSET, C.NON_CURRENT_ASSET),
        "liabilities": section(C.CURRENT_LIABILITY, C.NON_CURRENT_LIABILITY),
        "total_current_assets": _q(current_assets),
        "total_non_current_assets": _q(non_current_assets),
        "total_current_liabilities": _q(current_liabilities),
        "total_non_current_liabilities": _q(non_current_liabilities),
        "total_assets": _q(assets),
        "total_liabilities": _q(liabilities),
        "contributed_equity": _q(contributed_equity),
        "retained_earnings": _q(retained_earnings),
        "total_equity": _q(total_equity),
        "working_capital": _q(current_assets - current_liabilities),
        "current_ratio": ratio(current_assets, current_liabilities),
        "quick_ratio": ratio(quick_assets, current_liabilities),
        "balanced": _q(assets) == _q(liabilities + total_equity),
    }


def _receivable_and_payable(organization: Organization, as_of: date) -> tuple[Decimal, Decimal]:
    """Outstanding AR (from the ledger's control account) and AP (from open bills)."""
    balances = {b.code: b for b in account_balances(organization, end=as_of)}
    # 1400 under the statutory chart — 1100 is now Cash on Hand, so reading it
    # here reported the cash balance as money customers owed us.
    ar = balances["1400"].signed if "1400" in balances else ZERO
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
    Stock turns / GMROI use the standard pharmacy formulas:
      stock_turns = COGS(period) / avg_inventory_value * (365 / days)
      gmroi       = gross_margin_pct * stock_turns
    """
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    current = profit_and_loss(organization, start=start, end=end)
    previous = profit_and_loss(organization, start=prev_start, end=prev_end)
    receivable, payable = _receivable_and_payable(organization, end)

    dso = _q(receivable / current["revenue"] * days) if current["revenue"] else ZERO
    dpo = _q(payable / current["cogs"] * days) if current["cogs"] else ZERO

    # Operational KPIs the leader needs at a glance: cash, payroll liability,
    # inventory value, stock turns, GMROI.
    cash_on_hand = _cash_on_hand(organization)
    payroll_liability = _payroll_liability(organization)
    inventory_value = _inventory_value(organization)
    annualiser = Decimal("365") / Decimal(str(days)) if days else Decimal("0")
    stock_turns = _q(current["cogs"] / inventory_value * annualiser) if inventory_value else ZERO
    gmroi = (
        _q(current["gross_margin_pct"] * stock_turns)
        if current["gross_margin_pct"] and stock_turns
        else ZERO
    )

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
        "cash_on_hand": cash_on_hand,
        "payroll_liability": payroll_liability,
        "inventory_value": inventory_value,
        "stock_turns": stock_turns,
        "gmroi": gmroi,
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


def _cash_on_hand(organization: Organization) -> Decimal:
    """Sum of every active bank/MoMo/cash account's running cash-book balance."""
    from apps.finance.models import BankAccount
    from apps.finance.services import cash_book_lines

    total = Decimal("0")
    for acc in BankAccount.objects.filter(organization=organization, is_active=True):
        rows = cash_book_lines(acc)
        if rows:
            total += rows[-1]["running_balance"]
        else:
            total += acc.opening_balance
    return _q(total)


def _payroll_liability(organization: Organization) -> Decimal:
    """Outstanding payroll liabilities: net pay payable + statutory payables.

    Sums the signed balance of the statutory sub-ledger (PAYE, RSSB pension and
    maternity, CBHI, occupational hazards, RAMA) plus net pay payable.
    Liabilities carry a credit normal balance, so their signed value is already
    positive when owed. 2100 is trade payables, not payroll — including it
    double-counted supplier debt as a payroll liability."""
    codes = {"2200", "2210", "2220", "2230", "2240", "2250", "2600"}
    rows = account_balances(organization, end=timezone.localdate())
    total = sum((r.signed for r in rows if r.code in codes), Decimal("0"))
    return _q(total)


def _inventory_value(organization: Organization) -> Decimal:
    """On-hand × wholesale_cost across every active batch in the org. Batches
    with no recorded cost contribute zero (their stock is still tracked
    physically, but the GL can't value what has no cost stamp)."""
    from apps.inventory.models import InventoryBatch

    total = InventoryBatch.objects.filter(
        organization=organization,
        status=InventoryBatch.Status.ACTIVE,
        quantity_available__gt=0,
    ).aggregate(
        v=Coalesce(
            Sum(
                Case(
                    When(
                        wholesale_cost__isnull=False,
                        then=(F("quantity_available") * F("wholesale_cost")),
                    ),
                    output_field=_MONEY,
                )
            ),
            0,
            output_field=_MONEY,
        )
    )[
        "v"
    ] or Decimal(
        "0"
    )
    return _q(total)


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
    # Cash, bank and mobile money, plus any per-account sub-ledger children
    # (e.g. "1200-EQUITY-001"). Under the statutory chart these are 11xx-13xx;
    # the old single "1000" code no longer exists, which silently made every
    # cash-flow statement read zero.
    cash_codes = set(
        Account.objects.filter(
            Q(organization=organization),
            Q(code__in=["1100", "1200", "1300"])
            | Q(code__startswith="1100-")
            | Q(code__startswith="1200-")
            | Q(code__startswith="1300-"),
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

    # Eliminate trade between members of the group. Summing the branches counts a
    # depot's sale to its own retail branch as group revenue and the branch's
    # purchase as group cost — the same goods twice on their way through one
    # business. A group has not earned anything until it sells to someone outside
    # itself, so those internal legs come back out here.
    eliminations = intercompany_eliminations(organizations, start=start, end=end)
    gross = {k: _q(v) for k, v in totals.items()}
    consolidated_totals = dict(gross)
    consolidated_totals["revenue"] = _q(gross["revenue"] - eliminations["revenue"])
    consolidated_totals["cogs"] = _q(gross["cogs"] - eliminations["cogs"])
    consolidated_totals["gross_profit"] = _q(
        consolidated_totals["revenue"] - consolidated_totals["cogs"]
    )
    consolidated_totals["net_profit"] = _q(gross["net_profit"] - eliminations["profit_effect"])
    # Intercompany receivables and payables are the same debt seen from both ends.
    consolidated_totals["total_assets"] = _q(gross["total_assets"] - eliminations["receivable"])
    consolidated_totals["total_liabilities"] = _q(
        gross["total_liabilities"] - eliminations["payable"]
    )

    group_revenue = consolidated_totals["revenue"]
    return {
        "start": start,
        "end": end,
        "branches": per_branch,
        # What the branches add up to before anything is netted off.
        "gross_totals": gross,
        "eliminations": eliminations,
        "totals": consolidated_totals,
        "group_gross_margin_pct": (
            _q(consolidated_totals["gross_profit"] / group_revenue * 100) if group_revenue else ZERO
        ),
        "group_net_margin_pct": (
            _q(consolidated_totals["net_profit"] / group_revenue * 100) if group_revenue else ZERO
        ),
    }


def intercompany_eliminations(
    organizations: list[Organization], *, start: date, end: date
) -> dict[str, Any]:
    """Trade between members of the group, which must not appear in group results.

    An invoice raised by one group member on another is identified directly: both
    the seller (``organization``) and the buyer (``customer``) are inside the
    consolidation set.

    What is eliminated here:

    * **Revenue and cost** — the seller's revenue and the buyer's matching cost,
      netted so group turnover reflects only sales to outside customers.
    * **Receivables and payables** — the same debt recorded twice, once as an
      asset and once as a liability. It cancels.

    What is **not** eliminated, and is reported rather than hidden: **unrealised
    profit in closing stock**. Goods transferred at a margin and still sitting on
    the buying branch's shelf carry profit the group has not actually earned.
    Removing it correctly needs the transfer price of each remaining batch, which
    the stock records do not yet carry. ``unrealised_profit_note`` says so
    explicitly, because a consolidation that quietly ignores a known limitation is
    worse than one that names it.
    """
    from .models import CustomerInvoice

    ids = [o.pk for o in organizations]
    if len(ids) < 2:
        return {
            "revenue": ZERO,
            "cogs": ZERO,
            "profit_effect": ZERO,
            "receivable": ZERO,
            "payable": ZERO,
            "invoice_count": 0,
            "unrealised_profit_note": "",
        }

    internal = CustomerInvoice.objects.filter(
        organization_id__in=ids,
        customer_id__in=ids,
        invoice_date__gte=start,
        invoice_date__lte=end,
    ).exclude(status=CustomerInvoice.Status.CANCELLED)

    net_of_vat = ZERO
    outstanding = ZERO
    count = 0
    for invoice in internal:
        count += 1
        # VAT on an internal invoice is recovered by the buyer, so it never was
        # group income; strip it before eliminating.
        net_of_vat += _q(invoice.total_amount) - _q(invoice.vat_amount)
        outstanding += _q(invoice.total_amount) - _q(getattr(invoice, "amount_paid", ZERO))

    unrealised = unrealised_profit_in_stock(organizations, as_of=end)

    return {
        "revenue": _q(net_of_vat),
        # The buyer booked the same amount as its cost of purchase, so removing
        # both legs leaves group profit unchanged — which is the correct result
        # for goods that have been sold on outside the group.
        "cogs": _q(net_of_vat),
        # Goods still sitting inside the group carry the seller's margin. The
        # group has not earned that, so it comes out of group profit.
        "profit_effect": _q(unrealised["unrealised_profit"]),
        "receivable": _q(outstanding),
        "payable": _q(outstanding),
        "invoice_count": count,
        "unrealised_profit": str(_q(unrealised["unrealised_profit"])),
        "unrealised_detail": unrealised,
        "unrealised_profit_note": unrealised["note"],
    }


def unrealised_profit_in_stock(organizations: list[Organization], *, as_of: date) -> dict[str, Any]:
    """Margin sitting in stock that one group member bought from another.

    When a depot sells to its own branch at a markup, the branch carries the goods
    at the transfer price. Until they are sold to someone outside the group, that
    markup is not profit the group has earned — it is one pocket paying another.

    ``InventoryBatch.origin_unit_cost`` records what the selling entity itself
    paid, which is what makes the elimination possible. Batches transferred before
    that field existed have no origin cost; those are counted and reported rather
    than assumed to be zero-margin, because assuming would understate the
    adjustment and nobody would ever know.
    """
    from apps.inventory.models import InventoryBatch

    ids = [o.pk for o in organizations]
    if len(ids) < 2:
        return {
            "unrealised_profit": ZERO,
            "batches": 0,
            "unmeasured_batches": 0,
            "stock_at_transfer_price": ZERO,
            "note": "",
        }

    batches = InventoryBatch.objects.filter(
        organization_id__in=ids,
        source_org_id__in=ids,
        quantity_available__gt=0,
    ).exclude(source_org_id=F("organization_id"))

    unrealised = ZERO
    at_transfer = ZERO
    measured = unmeasured = 0
    for batch in batches:
        quantity = Decimal(batch.quantity_available)
        transfer_price = _q(batch.wholesale_cost or 0)
        at_transfer += _q(transfer_price * quantity)
        if batch.origin_unit_cost is None or transfer_price == 0:
            unmeasured += 1
            continue
        measured += 1
        margin = transfer_price - _q(batch.origin_unit_cost)
        if margin > 0:
            unrealised += _q(margin * quantity)

    note = ""
    if unmeasured:
        note = (
            f"{unmeasured} transferred batch(es) carry no origin cost, so their margin "
            "is not eliminated. The adjustment below is therefore a floor, not the "
            "full figure."
        )

    return {
        "unrealised_profit": _q(unrealised),
        "batches": measured,
        "unmeasured_batches": unmeasured,
        "stock_at_transfer_price": _q(at_transfer),
        "note": note,
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


def inventory_valuation(organization: Organization) -> dict[str, Any]:
    """Inventory on hand × wholesale cost, broken down by product and storage
    zone. Powers the leader's 'how much is sitting on the shelf' question
    and the inventory-valuation statement tab.

    Batches without a recorded wholesale_cost contribute zero — they are still
    physically present, but the GL can't value what has no cost stamp.
    """
    from apps.inventory.models import InventoryBatch

    total = Decimal("0")
    total_units = 0
    per_product: dict[int, dict[str, Any]] = {}
    rows = InventoryBatch.objects.filter(
        organization=organization,
        status=InventoryBatch.Status.ACTIVE,
        quantity_available__gt=0,
    ).select_related("product", "storage_location")
    for b in rows:
        cost = b.wholesale_cost or Decimal("0")
        line_value = _q(cost * b.quantity_available)
        total += line_value
        total_units += b.quantity_available
        bucket = per_product.setdefault(
            b.product_id,
            {
                "product_id": b.product_id,
                "product_name": str(b.product),
                "units": 0,
                "value": ZERO,
                "batches": 0,
            },
        )
        bucket["units"] += b.quantity_available
        bucket["value"] += line_value
        bucket["batches"] += 1

    return {
        "as_of": timezone.localdate(),
        "total_units": total_units,
        "total_value": _q(total),
        "by_product": [
            {
                **v,
                "value": _q(v["value"]),
            }
            for v in sorted(per_product.values(), key=lambda x: x["value"], reverse=True)
        ],
    }


def vat_return(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Rwanda VAT return draft for the period.

    Splits the period's GL movement on the VAT Output (2300) and VAT Input
    (1350) control accounts per tax class — derived from posted journal
    entries, never stored twice. The accountant exports this for the RRA
    e-Tax filing; the liability carried forward is the running balance on
    the VAT Output control account.

    Returns a dict with output (per class + total), input (per class + total),
    withholding, net_payable, and a CSV-ready ``lines`` list.
    """
    from apps.finance.models import TaxPayment

    # Output side: every credit on VAT Output (2300) for the period, summed
    # per class. Memo text on the journal line carries the class letter (the
    # post_sale_journal path stores B-class on its own lines; A/C fall through
    # to Sales Revenue without a VAT Output line — they contribute 0).
    output_total = Decimal("0")
    output_by_class: dict[str, Decimal] = {"A": ZERO, "B": ZERO, "C": ZERO, "D": ZERO}
    output_lines = JournalLine.objects.filter(
        account__organization=organization,
        account__code="2300",
        side=JournalLine.Side.CREDIT,
        entry__organization=organization,
        entry__status=JournalEntry.Status.POSTED,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
    ).select_related("entry")
    for ln in output_lines:
        output_total += ln.amount
        # Memo looks like "VAT Output (18% on standard-rated lines)" — we
        # treat any VAT Output credit as B-class (18%) for now since the
        # retail POS only emits B-class VAT. Multi-class is supported in
        # the model; future SL splits can tag class here.
        output_by_class["B"] += ln.amount

    # Input side: every debit on VAT Input (1350) for the period.
    input_total = Decimal("0")
    input_by_class: dict[str, Decimal] = {"A": ZERO, "B": ZERO, "C": ZERO, "D": ZERO}
    input_lines = JournalLine.objects.filter(
        account__organization=organization,
        account__code="1350",
        side=JournalLine.Side.DEBIT,
        entry__organization=organization,
        entry__status=JournalEntry.Status.POSTED,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
    ).select_related("entry")
    for ln in input_lines:
        input_total += ln.amount
        # Memo is "VAT Input (class X)" — read the class from the memo.
        memo = ln.memo or ""
        for cls in ("A", "B", "C", "D"):
            if f"class {cls}" in memo:
                input_by_class[cls] += ln.amount
                break

    # Withholding: debits on WHT Payable (2500) for the period.
    wht_total = Decimal("0")
    wht_lines = JournalLine.objects.filter(
        account__organization=organization,
        account__code="2500",
        side=JournalLine.Side.DEBIT,
        entry__organization=organization,
        entry__status=JournalEntry.Status.POSTED,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
    )
    for ln in wht_lines:
        wht_total += ln.amount

    net_payable = output_total - input_total - wht_total
    running_carry = _payroll_liability_balance(organization, "2300") - _payroll_liability_balance(
        organization, "1350"
    )

    # Remittances in the period (for the register).
    payments = TaxPayment.objects.filter(
        organization=organization,
        paid_on__gte=start,
        paid_on__lte=end,
    )
    paid_in_period = sum((p.amount for p in payments), Decimal("0"))
    amount_due_after_payments = net_payable - paid_in_period

    csv_lines = [
        ["Section", "Class", "Taxable / Net", "VAT"],
    ]
    for cls in ("A", "B", "C", "D"):
        csv_lines.append(["Output", cls, "0.00", str(_q(output_by_class[cls]))])
        csv_lines.append(["Input", cls, "0.00", str(_q(input_by_class[cls]))])
    csv_lines.append(["Withholding", "-", "0.00", str(_q(wht_total))])
    csv_lines.append(["Net payable", "-", "0.00", str(_q(net_payable))])
    csv_lines.append(["Remitted in period", "-", "0.00", str(_q(paid_in_period))])
    csv_lines.append(
        ["Amount due after remittances", "-", "0.00", str(_q(amount_due_after_payments))]
    )

    return {
        "start": start,
        "end": end,
        "output_by_class": {k: _q(v) for k, v in output_by_class.items()},
        "input_by_class": {k: _q(v) for k, v in input_by_class.items()},
        "output_total": _q(output_total),
        "input_total": _q(input_total),
        "withholding_total": _q(wht_total),
        "net_payable": _q(net_payable),
        "paid_in_period": _q(paid_in_period),
        "amount_due_after_payments": _q(amount_due_after_payments),
        "running_carry_forward": _q(running_carry),
        "csv": csv_lines,
    }


def _payroll_liability_balance(organization: Organization, code: str) -> Decimal:
    """Signed balance of one control account (used by vat_return for the
    period-end carry-forward)."""
    rows = account_balances(organization, end=timezone.localdate())
    match = next((r for r in rows if r.code == code), None)
    return match.signed if match else Decimal("0")


# ---------------------------------------------------------------------------
# Accounts receivable reporting: aging + statement of account
# ---------------------------------------------------------------------------

# Upper bound (days past due) for each bucket; None means "everything older".
_AGING_BUCKETS: list[tuple[str, int | None]] = [
    ("current", 0),
    ("days_1_30", 30),
    ("days_31_60", 60),
    ("days_61_90", 90),
    ("days_90_plus", None),
]


def _bucket_for(days_past_due: int) -> str:
    """Name the aging bucket a given overdue age falls into."""
    if days_past_due <= 0:
        return "current"
    for name, upper in _AGING_BUCKETS[1:]:
        if upper is None or days_past_due <= upper:
            return name
    return "days_90_plus"


def ar_aging(organization: Organization, *, as_of: date | None = None) -> dict[str, Any]:
    """Age every open customer invoice for ``organization`` into buckets.

    Returns per-customer rows plus org-wide totals. Only the unpaid balance
    counts, so a part-paid invoice ages only what is still owed.
    """
    from apps.finance.models import CustomerInvoice  # local: avoids an import cycle

    as_of = as_of or timezone.localdate()
    zero = Decimal("0.00")
    totals: dict[str, Decimal] = {name: zero for name, _ in _AGING_BUCKETS}
    totals["outstanding"] = zero
    by_customer: dict[int, dict[str, Any]] = {}

    open_invoices = (
        CustomerInvoice.objects.filter(organization=organization)
        .exclude(status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED])
        .select_related("customer")
    )
    for invoice in open_invoices:
        due = (invoice.total_amount - invoice.amount_paid).quantize(Decimal("0.01"))
        if due <= 0:
            continue
        bucket = _bucket_for((as_of - invoice.due_date).days)

        row = by_customer.setdefault(
            invoice.customer_id,
            {
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer.name,
                **{name: zero for name, _ in _AGING_BUCKETS},
                "outstanding": zero,
            },
        )
        row[bucket] += due
        row["outstanding"] += due
        totals[bucket] += due
        totals["outstanding"] += due

    return {
        "organization_id": organization.pk,
        "as_of": as_of,
        "customers": sorted(by_customer.values(), key=lambda r: r["outstanding"], reverse=True),
        "totals": totals,
    }


def statement_of_account(
    organization: Organization,
    customer: Organization,
    *,
    start: date,
    end: date,
) -> dict[str, Any]:
    """A running statement of what a customer was invoiced and what they paid.

    ``opening_balance`` is everything owed before ``start``; each line then
    moves the running balance, and ``closing_balance`` is where it lands.
    """
    from apps.finance.models import CustomerInvoice, CustomerReceipt

    zero = Decimal("0.00")
    invoices = CustomerInvoice.objects.filter(organization=organization, customer=customer).exclude(
        status=CustomerInvoice.Status.CANCELLED
    )
    receipts = CustomerReceipt.objects.filter(
        invoice__organization=organization, invoice__customer=customer
    ).select_related("invoice")

    # Opening: invoices raised before the window, less receipts before it.
    opening = zero
    for inv in invoices.filter(invoice_date__lt=start):
        opening += inv.total_amount
    for rcp in receipts.filter(received_on__lt=start):
        opening -= rcp.amount
    opening = opening.quantize(Decimal("0.01"))

    lines: list[dict[str, Any]] = []
    for inv in invoices.filter(invoice_date__gte=start, invoice_date__lte=end):
        lines.append(
            {
                "date": inv.invoice_date,
                "kind": "INVOICE",
                "reference": inv.invoice_number,
                "debit": inv.total_amount,
                "credit": zero,
                "description": f"Invoice due {inv.due_date}",
            }
        )
    for rcp in receipts.filter(received_on__gte=start, received_on__lte=end):
        lines.append(
            {
                "date": rcp.received_on,
                "kind": "RECEIPT",
                "reference": rcp.receipt_number,
                "debit": zero,
                "credit": rcp.amount,
                "description": f"Receipt ({rcp.method}) on {rcp.invoice.invoice_number}",
            }
        )

    lines.sort(key=lambda ln: (ln["date"], ln["kind"]))
    running = opening
    for line in lines:
        running = (running + line["debit"] - line["credit"]).quantize(Decimal("0.01"))
        line["balance"] = running

    return {
        "organization_id": organization.pk,
        "customer_id": customer.pk,
        "customer_name": customer.name,
        "start": start,
        "end": end,
        "opening_balance": opening,
        "closing_balance": running.quantize(Decimal("0.01")),
        "lines": lines,
    }
