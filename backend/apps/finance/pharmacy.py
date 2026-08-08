"""Pharmacy finance analytics — the numbers that decide whether a pharmacy lives.

A pharmacy is not a generic retailer, and generic finance reporting misses the
things that actually kill one:

* **Inventory is 60–80% of current assets and it expires.** Stock that will not
  sell before its expiry date is not an asset, it is a loss waiting to be
  recognised. IAS 2 requires inventory at the *lower of cost and net realisable
  value*, so short-dated stock must be written down — and the owner needs to see
  the exposure long before the write-off lands.
* **Cash is trapped in the cycle, not in the P&L.** A pharmacy can be profitable
  and still fail, because it pays suppliers in 30 days, holds stock for 90, and
  waits 60 for an insurer. The **cash conversion cycle** is the number that says
  how many days of working capital the business must fund.
* **Insurer receivables behave nothing like customer receivables.** They are
  short-paid, rejected and resubmitted; ageing them in the same bucket as a cash
  customer hides the real collection problem.
* **Margin varies enormously by channel.** Generic vs brand, OTC vs prescription,
  cash vs insured — a blended gross margin tells the owner nothing actionable.

Everything here is derived from the ledger and the stock records; nothing is
stored twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.finance.reports import ZERO, _q, account_balances, profit_and_loss
from apps.iam.models import Organization

_MONEY: DecimalField = DecimalField(max_digits=16, decimal_places=2)

#: How short-dated stock is graded. A pharmacy cannot sell a 30-day-dated box
#: through normal retail, and most wholesalers will not take it back inside 90
#: days, so the provision ramps as the window closes.
EXPIRY_BANDS: list[tuple[str, int, Decimal]] = [
    ("expired", 0, Decimal("1.00")),
    ("0_30", 30, Decimal("0.75")),
    ("31_60", 60, Decimal("0.50")),
    ("61_90", 90, Decimal("0.25")),
    ("91_180", 180, Decimal("0.10")),
]


@dataclass(frozen=True)
class InventoryExposure:
    band: str
    label: str
    quantity: int
    cost_value: Decimal
    provision_rate: Decimal
    provision: Decimal


def _batch_value_expression() -> Any:
    """Quantity × unit cost, as a DB expression so we never pull whole batches."""
    return ExpressionWrapper(
        Coalesce(F("quantity_available"), 0) * Coalesce(F("wholesale_cost"), Decimal("0")),
        output_field=_MONEY,
    )


def inventory_expiry_exposure(
    organization: Organization, *, as_of: date | None = None
) -> dict[str, Any]:
    """Stock at risk of expiring, and the provision IAS 2 would require.

    The provision rate is a judgement, not a law — but making it explicit and
    banded is what turns "we lost 4m in expiries again" into a number the owner
    can act on while there is still time to discount, transfer or return.
    """
    from apps.inventory.models import InventoryBatch

    today = as_of or timezone.localdate()
    live = InventoryBatch.objects.filter(
        organization=organization, quantity_available__gt=0
    ).exclude(status=InventoryBatch.Status.RECALLED)

    total = live.aggregate(
        qty=Coalesce(Sum("quantity_available"), 0),
        value=Coalesce(Sum(_batch_value_expression()), Decimal("0"), output_field=_MONEY),
    )

    rows: list[InventoryExposure] = []
    previous_cutoff: date | None = None
    for band, days, rate in EXPIRY_BANDS:
        cutoff = today + timedelta(days=days)
        window = Q(expiry_date__lte=cutoff)
        if band == "expired":
            window = Q(expiry_date__lt=today)
        elif previous_cutoff is not None:
            window &= Q(expiry_date__gt=previous_cutoff)
        else:
            window &= Q(expiry_date__gte=today)

        agg = live.filter(window).aggregate(
            qty=Coalesce(Sum("quantity_available"), 0),
            value=Coalesce(Sum(_batch_value_expression()), Decimal("0"), output_field=_MONEY),
        )
        value = _q(agg["value"])
        rows.append(
            InventoryExposure(
                band=band,
                label={
                    "expired": "Already expired",
                    "0_30": "Expires within 30 days",
                    "31_60": "31–60 days",
                    "61_90": "61–90 days",
                    "91_180": "91–180 days",
                }[band],
                quantity=int(agg["qty"] or 0),
                cost_value=value,
                provision_rate=rate,
                provision=_q(value * rate),
            )
        )
        previous_cutoff = cutoff

    at_risk_value = sum((r.cost_value for r in rows), ZERO)
    provision = sum((r.provision for r in rows), ZERO)
    stock_value = _q(total["value"])

    return {
        "as_of": today,
        "stock_value": stock_value,
        "stock_quantity": int(total["qty"] or 0),
        "at_risk_value": _q(at_risk_value),
        "at_risk_pct": _q(at_risk_value / stock_value * 100) if stock_value else ZERO,
        "suggested_provision": _q(provision),
        "provision_pct_of_stock": _q(provision / stock_value * 100) if stock_value else ZERO,
        "bands": [
            {
                "band": r.band,
                "label": r.label,
                "quantity": r.quantity,
                "cost_value": r.cost_value,
                "provision_rate": r.provision_rate,
                "provision": r.provision,
            }
            for r in rows
        ],
    }


def working_capital_cycle(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """The cash conversion cycle — how many days the owner's cash is tied up.

    ``CCC = DIO + DSO − DPO``

    * **DIO** days inventory outstanding — how long stock sits before it sells.
    * **DSO** days sales outstanding — how long customers and insurers take to pay.
    * **DPO** days payable outstanding — how long we take to pay suppliers.

    A positive cycle is working capital the business must fund out of its own
    pocket. For a pharmacy carrying 90 days of stock and waiting 60 days on
    insurance claims, that is the single biggest call on cash — and it never
    appears anywhere on the P&L.
    """
    from apps.finance.reports import _receivable_and_payable

    days = (end - start).days + 1
    pnl = profit_and_loss(organization, start=start, end=end)
    receivable, payable = _receivable_and_payable(organization, end)

    balances = {b.code: b for b in account_balances(organization, end=end)}
    inventory = balances["1500"].signed if "1500" in balances else ZERO

    cogs = pnl["cogs"]
    revenue = pnl["revenue"]

    # These are ratios, and a ratio needs a positive denominator to mean anything.
    # A period with no trading — or one whose cost of sales nets negative because
    # of a credit note — produces a number that is arithmetically valid and
    # completely false ("DPO −7,227 days"). Reporting *not computable* is the
    # honest answer; a dashboard that prints a confident absurdity is worse than
    # one that prints nothing.
    computable = cogs > 0 and revenue > 0

    dio = _q(inventory / cogs * days) if cogs > 0 else None
    dso = _q(receivable / revenue * days) if revenue > 0 else None
    dpo = _q(payable / cogs * days) if cogs > 0 else None
    ccc = _q((dio or ZERO) + (dso or ZERO) - (dpo or ZERO)) if computable else None

    # What that cycle costs to fund, at the daily rate of cost of sales.
    daily_cogs = _q(cogs / Decimal(days)) if days and cogs > 0 else ZERO
    funding_need = _q(daily_cogs * ccc) if ccc is not None and ccc > 0 else ZERO

    return {
        "start": start,
        "end": end,
        "days": days,
        "inventory_value": _q(inventory),
        "receivable": _q(receivable),
        "payable": _q(payable),
        "dio_days": dio,
        "dso_days": dso,
        "dpo_days": dpo,
        "cash_conversion_cycle_days": ccc,
        "working_capital_funding_need": funding_need,
        "computable": computable,
        "interpretation": (
            "Not enough trading in this period to measure the cycle — it needs "
            "both revenue and cost of sales to divide by."
            if ccc is None
            else (
                "Cash is released before stock is paid for — supplier terms are "
                "funding the business."
                if ccc <= 0
                else f"Roughly {ccc} days of cost of sales must be funded from the "
                "business's own cash at any one time."
            )
        ),
    }


def break_even(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Revenue needed to cover fixed costs, and how much headroom exists.

    Operating expenses are treated as fixed and cost of sales as variable, which
    is the right first approximation for a pharmacy: rent, salaries and licences
    do not move with the number of scripts dispensed, but the cost of the box does.
    """
    pnl = profit_and_loss(organization, start=start, end=end)
    revenue = pnl["revenue"]
    fixed_costs = pnl["operating_expenses"] + pnl["depreciation"]
    contribution_margin_pct = pnl["gross_margin_pct"]

    if contribution_margin_pct <= 0:
        break_even_revenue = None
        margin_of_safety_pct = None
    else:
        break_even_revenue = _q(fixed_costs / (contribution_margin_pct / Decimal("100")))
        margin_of_safety_pct = (
            _q((revenue - break_even_revenue) / revenue * 100) if revenue else ZERO
        )

    days = (end - start).days + 1
    return {
        "start": start,
        "end": end,
        "revenue": revenue,
        "fixed_costs": _q(fixed_costs),
        "contribution_margin_pct": contribution_margin_pct,
        "break_even_revenue": break_even_revenue,
        "break_even_revenue_per_day": (
            _q(break_even_revenue / Decimal(days)) if break_even_revenue and days else None
        ),
        "margin_of_safety_pct": margin_of_safety_pct,
        "is_above_break_even": bool(
            break_even_revenue is not None and revenue > break_even_revenue
        ),
    }


def margin_by_channel(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Gross margin split the ways a pharmacy actually earns it.

    Cost comes from the **batch the line was actually drawn from** (FEFO
    allocation), not a price-list guess — so the margin is the real one for that
    lot, including whatever landed cost the import carried.

    A blended margin hides the trade: generics carry far more margin than brands,
    and OTC more than prescription. This is what tells a pharmacist which
    substitution is worth making.
    """
    from apps.retail.models import Sale, SaleBatchAllocation

    allocations = (
        SaleBatchAllocation.objects.filter(
            sale_item__sale__organization=organization,
            sale_item__sale__created_at__date__gte=start,
            sale_item__sale__created_at__date__lte=end,
        )
        .exclude(sale_item__sale__status=Sale.Status.VOIDED)
        .select_related("sale_item__product", "batch")
    )

    buckets: dict[str, dict[str, Decimal]] = {}

    def bucket(key: str) -> dict[str, Decimal]:
        return buckets.setdefault(key, {"revenue": ZERO, "cost": ZERO, "units": ZERO})

    for allocation in allocations.iterator():
        item = allocation.sale_item
        product = item.product
        qty = Decimal(str(allocation.quantity or 0))
        revenue = Decimal(str(item.unit_price or 0)) * qty
        cost = Decimal(str(allocation.batch.wholesale_cost or 0)) * qty

        for key in (
            "Prescription" if product.requires_prescription else "OTC",
            "Brand" if product.brand_name else "Generic",
            "Controlled" if product.is_controlled_substance else "Uncontrolled",
        ):
            b = bucket(key)
            b["revenue"] += revenue
            b["cost"] += cost
            b["units"] += qty

    def row(key: str, values: dict[str, Decimal]) -> dict[str, Any]:
        revenue = _q(values["revenue"])
        cost = _q(values["cost"])
        margin = _q(revenue - cost)
        return {
            "channel": key,
            "revenue": revenue,
            "cost": cost,
            "gross_margin": margin,
            "gross_margin_pct": _q(margin / revenue * 100) if revenue else ZERO,
            "units": int(values["units"]),
        }

    rows = [row(k, v) for k, v in sorted(buckets.items())]
    return {
        "start": start,
        "end": end,
        "rows": rows,
        "note": (
            "Cost is the FEFO lot cost the line was actually drawn from. A batch "
            "received without a cost reads as 100% margin — fix that at goods "
            "receipt, not here."
        ),
    }


def retail_vs_wholesale(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """Split the two businesses a hybrid operator runs under one roof.

    A depot that also runs retail branches has two very different economics:
    wholesale moves volume at thin margin on credit terms; retail moves less at
    fat margin for cash. Consolidated revenue hides both. Wholesale is read off
    the B2B order book, retail off the counter.
    """
    from apps.distribution.models import StockOrder
    from apps.retail.models import Sale, SaleBatchAllocation

    retail_alloc = (
        SaleBatchAllocation.objects.filter(
            sale_item__sale__organization=organization,
            sale_item__sale__created_at__date__gte=start,
            sale_item__sale__created_at__date__lte=end,
        )
        .exclude(sale_item__sale__status=Sale.Status.VOIDED)
        .select_related("sale_item", "batch")
    )
    retail_revenue = ZERO
    retail_cost = ZERO
    for a in retail_alloc.iterator():
        qty = Decimal(str(a.quantity or 0))
        retail_revenue += Decimal(str(a.sale_item.unit_price or 0)) * qty
        retail_cost += Decimal(str(a.batch.wholesale_cost or 0)) * qty

    wholesale_orders = (
        StockOrder.objects.filter(
            depot=organization,
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .exclude(status=StockOrder.Status.CANCELLED)
        .prefetch_related("items")
    )
    wholesale_revenue = sum((Decimal(str(o.total_amount)) for o in wholesale_orders), ZERO)

    total = _q(retail_revenue + wholesale_revenue)
    retail_margin = _q(retail_revenue - retail_cost)

    return {
        "start": start,
        "end": end,
        "total_revenue": total,
        "rows": [
            {
                "channel": "Retail (counter)",
                "revenue": _q(retail_revenue),
                "cost": _q(retail_cost),
                "gross_margin": retail_margin,
                "gross_margin_pct": (
                    _q(retail_margin / retail_revenue * 100) if retail_revenue else ZERO
                ),
                "share_pct": _q(retail_revenue / total * 100) if total else ZERO,
            },
            {
                "channel": "Wholesale (B2B)",
                "revenue": _q(wholesale_revenue),
                "orders": wholesale_orders.count(),
                "share_pct": _q(wholesale_revenue / total * 100) if total else ZERO,
            },
        ],
    }


def branch_comparison(
    organizations: list[Organization], *, start: date, end: date
) -> dict[str, Any]:
    """HQ's view: every branch side by side on the numbers that matter.

    Consolidated totals tell the group how it did; this tells it *which branch*
    did it — and which one is quietly carrying dead stock or losing margin.
    """
    from apps.finance.reports import balance_sheet

    rows: list[dict[str, Any]] = []
    for org in organizations:
        pnl = profit_and_loss(org, start=start, end=end)
        sheet = balance_sheet(org, as_of=end)
        expiry = inventory_expiry_exposure(org, as_of=end)
        cycle = working_capital_cycle(org, start=start, end=end)
        rows.append(
            {
                "organization_id": org.pk,
                "organization": org.name,
                "type": org.type,
                "revenue": pnl["revenue"],
                "gross_profit": pnl["gross_profit"],
                "gross_margin_pct": pnl["gross_margin_pct"],
                "operating_expenses": pnl["operating_expenses"],
                "net_profit": pnl["net_profit"],
                "net_margin_pct": pnl["net_margin_pct"],
                "inventory_value": expiry["stock_value"],
                "expiry_at_risk": expiry["at_risk_value"],
                "expiry_at_risk_pct": expiry["at_risk_pct"],
                "cash_conversion_cycle_days": cycle["cash_conversion_cycle_days"],
                "cycle_computable": cycle["computable"],
                "current_ratio": sheet["current_ratio"],
                "quick_ratio": sheet["quick_ratio"],
            }
        )

    group_revenue = sum((r["revenue"] for r in rows), ZERO)
    for r in rows:
        r["revenue_share_pct"] = _q(r["revenue"] / group_revenue * 100) if group_revenue else ZERO
    rows.sort(key=lambda r: r["revenue"], reverse=True)

    return {
        "start": start,
        "end": end,
        "rows": rows,
        "group_revenue": _q(group_revenue),
        "group_net_profit": _q(sum((r["net_profit"] for r in rows), ZERO)),
        "group_inventory": _q(sum((r["inventory_value"] for r in rows), ZERO)),
        "group_expiry_at_risk": _q(sum((r["expiry_at_risk"] for r in rows), ZERO)),
    }


def capital_returns(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """What the owner's money earned — ROE, ROA, ROCE and GMROI.

    ROADMAP §9 asks for *"invested capital … ROI / ROE / GMROI"*. These are the
    ratios that answer "should my money be in this pharmacy at all", and each has
    a specific denominator that must not be swapped for a convenient one:

    * **ROE** = net profit ÷ shareholders' equity — the owner's own return.
    * **ROA** = net profit ÷ total assets — how hard every asset works.
    * **ROCE** = operating profit ÷ (total assets − current liabilities) — return
      on the capital actually employed, before financing choices distort it.
    * **GMROI** = gross margin ÷ average inventory at cost — the pharmacy-specific
      one: how many francs of margin each franc tied up in stock returns. Below
      1.0 the shelf is losing money.

    All are annualised from the period so a monthly view is comparable to a yearly
    one; a raw monthly ROE looks like a catastrophe next to an annual target.
    """
    from apps.finance.reports import balance_sheet

    days = (end - start).days + 1
    annualiser = Decimal("365") / Decimal(days) if days else ZERO

    pnl = profit_and_loss(organization, start=start, end=end)
    sheet = balance_sheet(organization, as_of=end)

    equity = sheet["total_equity"]
    total_assets = sheet["total_assets"]
    capital_employed = _q(total_assets - sheet["total_current_liabilities"])
    inventory = inventory_expiry_exposure(organization, as_of=end)["stock_value"]

    net_profit = pnl["net_profit"]
    operating_profit = pnl["operating_profit"]
    gross_profit = pnl["gross_profit"]

    def ret(numerator: Decimal, denominator: Decimal) -> Decimal | None:
        if not denominator:
            return None
        return _q(numerator * annualiser / denominator * 100)

    gmroi = _q(gross_profit * annualiser / inventory) if inventory else None

    return {
        "start": start,
        "end": end,
        "annualised": True,
        "equity": equity,
        "total_assets": total_assets,
        "capital_employed": capital_employed,
        "inventory_at_cost": inventory,
        "net_profit": net_profit,
        "operating_profit": operating_profit,
        "roe_pct": ret(net_profit, equity),
        "roa_pct": ret(net_profit, total_assets),
        "roce_pct": ret(operating_profit, capital_employed),
        "gmroi": gmroi,
        "gmroi_verdict": (
            None
            if gmroi is None
            else (
                "Each franc in stock returns less than a franc of margin — the shelf "
                "is not paying for itself."
                if gmroi < 1
                else "Stock is earning its keep."
            )
        ),
    }


def pharmacy_cockpit(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    """One call for the pharmacy owner's view: profit, cash cycle, expiry risk,
    break-even, and where the margin actually comes from."""
    from apps.finance.reports import balance_sheet, performance

    return {
        "organization_id": organization.pk,
        "organization": organization.name,
        "performance": performance(organization, start=start, end=end),
        "balance_sheet": balance_sheet(organization, as_of=end),
        "working_capital": working_capital_cycle(organization, start=start, end=end),
        "expiry_exposure": inventory_expiry_exposure(organization, as_of=end),
        "break_even": break_even(organization, start=start, end=end),
        "margin_by_channel": margin_by_channel(organization, start=start, end=end),
        "retail_vs_wholesale": retail_vs_wholesale(organization, start=start, end=end),
        "returns": capital_returns(organization, start=start, end=end),
    }
