"""What a person running a pharmacy actually needs to see when they sign in.

The dashboard returned ten flat scalars aggregated across every organization the
user could see, and three things were missing that each defeat the purpose:

**No time dimension.** Everything was *today*. "Sales today: RWF 840,000" does not
tell a manager whether that is a good day, because there is nothing to compare it
to.

**No per-branch split.** The view summed across every visible organization and
returned one number. It even computed ``org_count`` — so a group owner with four
pharmacies was told "4 organizations" and given a single total, with no way to see
which branch produced it. Comparing branches is the main thing a group owner does.

**No margin.** ``sales_today.total`` is revenue. For a pharmacy that is largely
determined by what the insurer reimburses; the number that decides whether the
business works is the gap between it and cost.

All three are computed here rather than in the view, so a management command or a
scheduled report can ask the same questions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

ZERO = Decimal("0.00")

#: Two weeks reads as a trend without becoming a chart nobody can label.
TREND_DAYS = 14


def _money(value: Decimal | int | float | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def cost_of_sales(sale_ids: list[int]) -> dict[int, Decimal]:
    """What the goods on each sale cost us, from the batches actually drawn.

    Cost comes from the allocation rather than from a product-level average
    because FEFO decides which batch went out of the door, and two batches of the
    same medicine bought months apart rarely cost the same.
    """
    from apps.retail.models import SaleBatchAllocation

    out: dict[int, Decimal] = defaultdict(lambda: ZERO)
    rows = (
        SaleBatchAllocation.objects.filter(sale_item__sale_id__in=sale_ids)
        .select_related("batch", "sale_item")
        .values("sale_item__sale_id", "quantity", "batch__wholesale_cost")
    )
    for row in rows:
        unit = Decimal(str(row["batch__wholesale_cost"] or 0))
        out[row["sale_item__sale_id"]] += unit * row["quantity"]
    return dict(out)


def sales_between(*, org_ids: list[int], start: date, end: date) -> list[Any]:
    from apps.retail.models import Sale

    return list(
        Sale.objects.filter(
            organization_id__in=org_ids,
            status=Sale.Status.COMPLETED,
            completed_at__date__gte=start,
            completed_at__date__lte=end,
        )
        .select_related("organization")
        .prefetch_related("items")
    )


def performance(*, org_ids: list[int], on: date | None = None) -> dict[str, Any]:
    """Today's trading, yesterday's for comparison, a trend, and a branch split."""
    today = on or timezone.localdate()
    start = today - timedelta(days=TREND_DAYS - 1)

    sales = sales_between(org_ids=org_ids, start=start, end=today)
    costs = cost_of_sales([s.pk for s in sales])

    by_day: dict[date, Decimal] = defaultdict(lambda: ZERO)
    by_branch: dict[int, dict[str, Any]] = {}
    revenue_today = margin_today = ZERO
    count_today = 0

    for sale in sales:
        day = timezone.localtime(sale.completed_at).date() if sale.completed_at else today
        revenue = _money(sale.total)
        cost = _money(costs.get(sale.pk))
        by_day[day] += revenue

        branch = by_branch.setdefault(
            sale.organization_id,
            {
                "organization": sale.organization_id,
                "name": sale.organization.name,
                "type": sale.organization.type,
                "revenue": ZERO,
                "cost": ZERO,
                "sales": 0,
            },
        )
        if day == today:
            branch["revenue"] += revenue
            branch["cost"] += cost
            branch["sales"] += 1
            revenue_today += revenue
            margin_today += revenue - cost
            count_today += 1

    yesterday = _money(by_day.get(today - timedelta(days=1)))
    week_ago = _money(by_day.get(today - timedelta(days=7)))

    branches = []
    for row in by_branch.values():
        revenue = _money(row["revenue"])
        margin = revenue - _money(row["cost"])
        branches.append(
            {
                "organization": row["organization"],
                "name": row["name"],
                "type": row["type"],
                "sales": row["sales"],
                "revenue": float(revenue),
                "margin": float(margin),
                "margin_pct": float(round(margin / revenue * 100, 1)) if revenue else 0.0,
            }
        )
    branches.sort(key=lambda b: b["revenue"], reverse=True)

    return {
        "today": {
            "sales": count_today,
            "revenue": float(revenue_today),
            "margin": float(margin_today),
            "margin_pct": (
                float(round(margin_today / revenue_today * 100, 1)) if revenue_today else 0.0
            ),
        },
        # Stated as "what it was" rather than as a percentage change: a jump from
        # RWF 2,000 to RWF 6,000 is +200% and means nothing.
        "compared": {
            "yesterday": float(yesterday),
            "same_day_last_week": float(week_ago),
        },
        "trend": [
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "revenue": float(_money(by_day.get(start + timedelta(days=offset)))),
            }
            for offset in range(TREND_DAYS)
        ],
        "by_branch": branches,
    }


def expiry_exposure(*, org_ids: list[int], horizon_days: int = 90) -> dict[str, Any]:
    """Money that will walk off the shelf if nothing is done, in bands.

    Bands rather than one number because the action differs: 0–30 days is
    discount-and-move, 30–90 is plan around, already expired is a write-off that
    should already have happened.
    """
    from apps.inventory.models import InventoryBatch

    today = timezone.localdate()
    batches = InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        quantity_available__gt=0,
        expiry_date__lte=today + timedelta(days=horizon_days),
    ).values("expiry_date", "quantity_available", "wholesale_cost")

    bands = {"expired": ZERO, "within_30": ZERO, "within_60": ZERO, "within_90": ZERO}
    units: dict[str, Decimal] = {key: Decimal(0) for key in bands}
    for row in batches:
        value = Decimal(str(row["wholesale_cost"] or 0)) * row["quantity_available"]
        days = (row["expiry_date"] - today).days
        key = (
            "expired"
            if days < 0
            else "within_30" if days <= 30 else "within_60" if days <= 60 else "within_90"
        )
        bands[key] += value
        units[key] += row["quantity_available"]

    return {
        "bands": [
            {"band": key, "value": float(_money(bands[key])), "units": units[key]}
            for key in ("expired", "within_30", "within_60", "within_90")
        ],
        "total_at_risk": float(_money(sum(bands.values(), ZERO))),
    }
