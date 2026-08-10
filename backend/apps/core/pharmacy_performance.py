"""How is my pharmacy doing?

An owner asking this does not want a trial balance. They want to know whether
the month is better than the last one, which medicines are carrying the shop,
and what is going wrong that they have not noticed.

The figures are the same ones the finance reports use. What differs is the
question they are arranged to answer.

**On the score.** A single percentage is genuinely useful — it is the thing
somebody checks in five seconds — and genuinely dangerous, because a number
with no stated method gets treated as a rating. So: it is called an
*operational health* score, never a credit score or a compliance rating; every
component is returned alongside it with its own figure and the rule that
produced it; and where there is not enough trading history to judge a component,
it is left out of the average rather than scored zero. A pharmacy that opened
last week should not be told it is failing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

ZERO = Decimal("0.00")


def _money(value: Any, currency: str = "RWF") -> dict[str, str]:
    return {"amount": f"{Decimal(str(value or 0)):.2f}", "currency": currency}


def _change(now: Decimal, before: Decimal) -> float | None:
    """Percentage change, or nothing when there is no base.

    Never 0 for "there was no previous period" — that reads as "unchanged",
    which is a different and misleading claim.
    """
    if before <= 0:
        return None
    return float(((now - before) / before * 100).quantize(Decimal("0.1")))


def _period(org_ids: list[int], start: date, end: date) -> dict[str, Any]:
    from apps.retail.models import Sale

    sales = Sale.objects.filter(
        organization_id__in=org_ids,
        status=Sale.Status.COMPLETED,
        completed_at__date__gte=start,
        completed_at__date__lte=end,
    ).prefetch_related("items__allocations__batch", "items__product")

    revenue = cost = ZERO
    transactions = 0
    by_product: dict[int, dict[str, Any]] = {}

    for sale in sales:
        transactions += 1
        revenue += Decimal(str(sale.total))
        for item in sale.items.all():
            line_revenue = Decimal(str(item.unit_price)) * Decimal(str(item.quantity))
            line_cost = ZERO
            for allocation in item.allocations.all():
                line_cost += Decimal(str(allocation.batch.wholesale_cost or 0)) * Decimal(
                    str(allocation.quantity)
                )
            cost += line_cost
            row = by_product.setdefault(
                item.product_id,
                {
                    "product": item.product_id,
                    "name": (item.product.generic_name or str(item.product)).strip(),
                    "revenue": ZERO,
                    "cost": ZERO,
                    "units": Decimal("0"),
                },
            )
            row["revenue"] += line_revenue
            row["cost"] += line_cost
            row["units"] += Decimal(str(item.quantity_base or item.quantity or 0))

    gross = revenue - cost
    return {
        "revenue": revenue,
        "cost": cost,
        "gross_profit": gross,
        "margin_pct": (
            float((gross / revenue * 100).quantize(Decimal("0.1"))) if revenue > 0 else None
        ),
        "transactions": transactions,
        "average_basket": (revenue / transactions) if transactions else ZERO,
        "by_product": by_product,
    }


def _best_sellers(by_product: dict[int, dict[str, Any]], currency: str) -> list[dict[str, Any]]:
    """Ranked by gross profit, not by revenue.

    A pharmacy's biggest seller by turnover is often its thinnest earner — a
    high-volume, low-margin staple. Ranking by what each line actually
    contributes is the list an owner can make a decision from.
    """
    rows = sorted(by_product.values(), key=lambda r: r["revenue"] - r["cost"], reverse=True)
    return [
        {
            "name": row["name"],
            "revenue": _money(row["revenue"], currency),
            "gross_profit": _money(row["revenue"] - row["cost"], currency),
            "units": str(row["units"].normalize()),
            "margin_pct": (
                float(
                    ((row["revenue"] - row["cost"]) / row["revenue"] * 100).quantize(Decimal("0.1"))
                )
                if row["revenue"] > 0
                else None
            ),
        }
        for row in rows[:5]
    ]


def _problems(org_ids: list[int], today: date, currency: str) -> list[dict[str, Any]]:
    """What is going wrong, with the money attached to it."""
    from apps.distribution.models import StockOrder
    from apps.insurance.models import Claim
    from apps.inventory.models import InventoryBatch

    found: list[dict[str, Any]] = []

    horizon = today + timedelta(days=90)
    at_risk = ZERO
    count = 0
    for batch in InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        status=InventoryBatch.Status.ACTIVE,
        expiry_date__gte=today,
        expiry_date__lte=horizon,
        quantity_available__gt=0,
    ).only("quantity_available", "wholesale_cost"):
        at_risk += Decimal(str(batch.wholesale_cost or 0)) * Decimal(str(batch.quantity_available))
        count += 1
    if count:
        found.append(
            {
                "kind": "expiry_risk",
                "label": f"{count} batch(es) expire within 90 days",
                "value": _money(at_risk, currency),
                "to": "/catalog/expiry",
            }
        )

    overdue = ZERO
    overdue_count = 0
    for order in (
        StockOrder.objects.filter(retail_id__in=org_ids, payment_due_date__lt=today)
        .exclude(payment_status=StockOrder.PaymentStatus.PAID)
        .prefetch_related("items")
    ):
        overdue += Decimal(str(order.amount_due))
        overdue_count += 1
    if overdue_count:
        found.append(
            {
                "kind": "overdue_supplier",
                "label": f"{overdue_count} supplier invoice(s) past their due date",
                "value": _money(overdue, currency),
                "to": "/finance/payables",
            }
        )

    rejected = Claim.objects.filter(organization_id__in=org_ids, status=Claim.Status.REJECTED)
    rejected_count = rejected.count()
    if rejected_count:
        found.append(
            {
                "kind": "rejected_claims",
                "label": f"{rejected_count} insurance claim(s) were rejected",
                "value": _money(rejected.aggregate(total=Sum("claimed_amount"))["total"], currency),
                "to": "/insurance/claims",
            }
        )

    return found


def _health(
    *, this_month: dict[str, Any], last_month: dict[str, Any], org_ids: list[int], today: date
) -> dict[str, Any]:
    """An operational health score, with its working shown.

    Each component scores 0–100 against a stated rule. A component with too
    little evidence returns None and is dropped from the average — a pharmacy
    with no trading history is not unhealthy, it is new, and scoring it zero
    would be a lie dressed as arithmetic.
    """
    from apps.inventory.models import InventoryBatch, PharmacyProduct

    components: list[dict[str, Any]] = []

    def add(name: str, score: float | None, basis: str) -> None:
        components.append(
            {"name": name, "score": None if score is None else round(score), "basis": basis}
        )

    # Margin: 25% is a healthy community-pharmacy gross margin; below 10% is thin.
    margin = this_month["margin_pct"]
    add(
        "Margin",
        None if margin is None else max(0.0, min(100.0, (margin / 25.0) * 100)),
        "Gross margin this month against 25%, a healthy community-pharmacy margin.",
    )

    # Growth: this month against last, capped so one good month is not 100.
    growth = _change(this_month["revenue"], last_month["revenue"])
    add(
        "Sales trend",
        None if growth is None else max(0.0, min(100.0, 50 + growth * 2)),
        "Sales this month against the same stretch of last month; 50 is flat.",
    )

    # Availability: what proportion of what you stock is actually in stock.
    listings = PharmacyProduct.objects.filter(organization_id__in=org_ids, is_active=True)
    listed = listings.count()
    if listed:
        in_stock = (
            InventoryBatch.objects.filter(
                organization_id__in=org_ids,
                status=InventoryBatch.Status.ACTIVE,
                expiry_date__gte=today,
                quantity_available__gt=0,
                product_id__in=listings.values_list("product_id", flat=True),
            )
            .values("product_id")
            .distinct()
            .count()
        )
        add(
            "Availability",
            in_stock / listed * 100,
            f"{in_stock} of {listed} medicine(s) you list are on the shelf today.",
        )
    else:
        add("Availability", None, "No medicines listed yet.")

    # Expiry control: value expiring within 90 days against total stock value.
    total_value = ZERO
    expiring_value = ZERO
    horizon = today + timedelta(days=90)
    for batch in InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        status=InventoryBatch.Status.ACTIVE,
        quantity_available__gt=0,
    ).only("quantity_available", "wholesale_cost", "expiry_date"):
        value = Decimal(str(batch.wholesale_cost or 0)) * Decimal(str(batch.quantity_available))
        total_value += value
        if batch.expiry_date and today <= batch.expiry_date <= horizon:
            expiring_value += value
    add(
        "Expiry control",
        None if total_value <= 0 else float(100 - (expiring_value / total_value * 100)),
        "Share of stock value not expiring within 90 days.",
    )

    scored = [c["score"] for c in components if c["score"] is not None]
    overall = round(sum(scored) / len(scored)) if scored else None
    return {
        "score": overall,
        "components": components,
        "caveat": (
            "An operational reading of this pharmacy's own data, not a credit score or a "
            "regulatory rating. Every component and its rule is listed above."
        ),
    }


def pharmacy_performance(user: Any, *, on: date | None = None) -> dict[str, Any]:
    from apps.iam.scoping import organizations_visible_to

    orgs = organizations_visible_to(user)
    org_ids = list(orgs.values_list("id", flat=True))
    today = on or timezone.localdate()
    home = user.organization
    currency = (home.currency if home else "RWF") or "RWF"

    month_start = today.replace(day=1)
    days_in = (today - month_start).days
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    # Compare like with like: the same number of days into the previous month,
    # so the 3rd is not judged against a full month and told sales collapsed.
    last_month_same_stretch_end = min(last_month_start + timedelta(days=days_in), last_month_end)

    this_month = _period(org_ids, month_start, today)
    last_month = _period(org_ids, last_month_start, last_month_same_stretch_end)

    stock_value = ZERO
    from apps.inventory.models import InventoryBatch

    for batch in InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        status=InventoryBatch.Status.ACTIVE,
        quantity_available__gt=0,
    ).only("quantity_available", "wholesale_cost"):
        stock_value += Decimal(str(batch.wholesale_cost or 0)) * Decimal(
            str(batch.quantity_available)
        )

    return {
        "as_of": today.isoformat(),
        "currency": currency,
        "period": {
            "from": month_start.isoformat(),
            "to": today.isoformat(),
            "compared_with": (
                f"{last_month_start.isoformat()} to {last_month_same_stretch_end.isoformat()}"
            ),
            "note": (
                "Compared against the same number of days into last month, so an early "
                "date is not judged against a whole month."
            ),
        },
        "revenue": _money(this_month["revenue"], currency),
        "revenue_change_pct": _change(this_month["revenue"], last_month["revenue"]),
        "gross_profit": _money(this_month["gross_profit"], currency),
        "gross_profit_change_pct": _change(this_month["gross_profit"], last_month["gross_profit"]),
        "margin_pct": this_month["margin_pct"],
        "margin_change_pts": (
            None
            if this_month["margin_pct"] is None or last_month["margin_pct"] is None
            else round(this_month["margin_pct"] - last_month["margin_pct"], 1)
        ),
        "transactions": this_month["transactions"],
        "transactions_change_pct": _change(
            Decimal(this_month["transactions"]), Decimal(last_month["transactions"])
        ),
        "average_basket": _money(this_month["average_basket"], currency),
        "stock_value": _money(stock_value, currency),
        "best_sellers": _best_sellers(this_month["by_product"], currency),
        "problems": _problems(org_ids, today, currency),
        "health": _health(
            this_month=this_month, last_month=last_month, org_ids=org_ids, today=today
        ),
    }
