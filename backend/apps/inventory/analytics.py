"""Inventory analytics — the read-side maths behind replenishment and cold chain.

Everything here derives from data the ledger already holds (``StockMovement``,
``InventoryBatch``) so no figure is hand-maintained:

* :func:`demand_statistics`  — average daily demand and its variability per product.
* :func:`recompute_reorder_rules` — writes min/max/reorder-point/safety-stock and the
  ABC/XYZ classes back onto :class:`~apps.inventory.models.ReorderRule`.
* :func:`suggested_orders`  — what to buy right now, and why.
* :func:`slow_and_dead_stock` / :func:`near_expiry_actions` — the two "money sitting
  still" lists a stock controller works from.
* :func:`mean_kinetic_temperature` — the Arrhenius-weighted single figure that
  expresses cumulative thermal stress over a window of readings.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from apps.iam.models import Organization
from apps.inventory.models import (
    InventoryBatch,
    ReorderRule,
    StockMovement,
    TemperatureLog,
)

# Demand-consuming movements: what actually left the building for a customer or a
# branch. Wastage and adjustments are losses, not demand — counting them would
# inflate the reorder point and have us buy stock to replace what we spilled.
DEMAND_TYPES = (StockMovement.Type.SALE, StockMovement.Type.TRANSFER_OUT)

# Normal-distribution z-scores for the common service levels. Safety stock is
# z × σ_demand × √lead-time, the textbook formula for a fixed lead time.
_Z_SCORES: list[tuple[float, float]] = [
    (99.9, 3.09),
    (99.0, 2.33),
    (98.0, 2.05),
    (97.0, 1.88),
    (95.0, 1.65),
    (90.0, 1.28),
    (85.0, 1.04),
    (80.0, 0.84),
    (75.0, 0.67),
    (50.0, 0.0),
]


def z_for_service_level(percent: float) -> float:
    """Z-score for a service level, taking the nearest tabulated rung."""
    return min(_Z_SCORES, key=lambda row: abs(row[0] - percent))[1]


def _demand_rows(organization: Organization, *, days: int) -> QuerySet[StockMovement]:
    since = timezone.now() - timedelta(days=days)
    return StockMovement.objects.filter(
        organization=organization,
        movement_type__in=DEMAND_TYPES,
        occurred_at__gte=since,
    )


def demand_statistics(organization: Organization, *, days: int = 90) -> dict[int, dict[str, Any]]:
    """Per-product demand over the window, bucketed by day.

    Returns ``{product_id: {total, avg_daily, std_dev, cv, days_with_demand,
    last_movement_on}}``. ``cv`` (coefficient of variation = σ/μ) is the XYZ input:
    a product whose weekly draw barely changes has a low CV; one that moves in
    unpredictable bursts has a high one.
    """
    per_product_per_day: dict[int, dict[date, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: Decimal(0))
    )
    last_seen: dict[int, date] = {}

    for mv in _demand_rows(organization, days=days).values_list(
        "product_id", "quantity_delta", "occurred_at"
    ):
        product_id, delta, occurred = mv
        day = timezone.localtime(occurred).date()
        per_product_per_day[product_id][day] += abs(delta)
        if product_id not in last_seen or day > last_seen[product_id]:
            last_seen[product_id] = day

    stats: dict[int, dict[str, Any]] = {}
    for product_id, by_day in per_product_per_day.items():
        # Zero-demand days count: they are exactly what makes demand erratic.
        series = [
            float(by_day.get(timezone.localdate() - timedelta(days=i), Decimal(0)))
            for i in range(days)
        ]
        total = sum(series)
        mean = total / days if days else 0.0
        variance = sum((v - mean) ** 2 for v in series) / days if days else 0.0
        std_dev = math.sqrt(variance)
        stats[product_id] = {
            "total": total,
            "avg_daily": mean,
            "std_dev": std_dev,
            "cv": (std_dev / mean) if mean > 0 else 0.0,
            "days_with_demand": sum(1 for v in series if v > 0),
            "last_movement_on": last_seen.get(product_id),
        }
    return stats


def _abc_class(cumulative_share: float) -> str:
    """Pareto split on cumulative consumption value: 80 / 95 / 100."""
    if cumulative_share <= 80.0:
        return ReorderRule.ABC.A
    if cumulative_share <= 95.0:
        return ReorderRule.ABC.B
    return ReorderRule.ABC.C


def _xyz_class(cv: float) -> str:
    if cv < 0.5:
        return ReorderRule.XYZ.X
    if cv <= 1.0:
        return ReorderRule.XYZ.Y
    return ReorderRule.XYZ.Z


def _unit_cost(organization: Organization, product_id: int) -> Decimal:
    """Latest known cost for a product at this org (newest costed batch wins)."""
    batch = (
        InventoryBatch.objects.filter(
            organization=organization, product_id=product_id, wholesale_cost__isnull=False
        )
        .order_by("-created_at")
        .first()
    )
    return batch.wholesale_cost if batch and batch.wholesale_cost else Decimal("0")


def on_hand_map(organization: Organization) -> dict[int, int]:
    """Sellable on-hand per product: ACTIVE, unexpired batches only."""
    rows = (
        InventoryBatch.objects.filter(
            organization=organization,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        )
        .values("product_id")
        .annotate(total=Sum("quantity_available"))
    )
    return {r["product_id"]: int(r["total"] or 0) for r in rows}


def recompute_reorder_rules(
    organization: Organization, *, days: int = 90, create_missing: bool = True
) -> dict[str, Any]:
    """Recompute demand stats, ABC/XYZ and the reorder levers for an organization.

    Rules with ``is_auto_calculated=False`` keep their hand-set min/max/ROP — only
    the observed statistics and classes are refreshed on them, so a buyer's
    deliberate override is never silently overwritten.
    """
    stats = demand_statistics(organization, days=days)

    # Annual consumption value drives ABC. Extrapolate the window to a year so a
    # 90-day sample and a 365-day sample rank products the same way.
    scale = Decimal(365) / Decimal(days or 1)
    valued: list[tuple[int, Decimal]] = []
    for product_id, s in stats.items():
        cost = _unit_cost(organization, product_id)
        valued.append((product_id, (Decimal(s["total"]) * cost * scale).quantize(Decimal("0.01"))))
    valued.sort(key=lambda row: row[1], reverse=True)
    grand_total = sum((v for _, v in valued), Decimal("0"))

    abc_by_product: dict[int, str] = {}
    running = Decimal("0")
    for product_id, value in valued:
        # Classify on the cumulative share *reached before* this product, so the
        # item that carries the class boundary belongs to the class it completes.
        # Grading on the share after adding it would demote the single biggest
        # consumer — the most A of all A items — to C.
        share = float(running / grand_total * 100) if grand_total > 0 else 100.0
        abc_by_product[product_id] = _abc_class(share)
        running += value

    # Products with stock but no demand in the window are C/Z by definition.
    for product_id in on_hand_map(organization):
        abc_by_product.setdefault(product_id, ReorderRule.ABC.C)

    updated = created = 0
    now = timezone.now()
    for product_id, abc in abc_by_product.items():
        s = stats.get(product_id, {"avg_daily": 0.0, "std_dev": 0.0, "cv": 0.0, "total": 0})
        rule = ReorderRule.objects.filter(organization=organization, product_id=product_id).first()
        if rule is None:
            if not create_missing:
                continue
            rule = ReorderRule(organization=organization, product_id=product_id)
            created += 1
        else:
            updated += 1

        annual_value = next((v for pid, v in valued if pid == product_id), Decimal("0"))
        rule.avg_daily_demand = Decimal(str(round(s["avg_daily"], 4)))
        rule.demand_std_dev = Decimal(str(round(s["std_dev"], 4)))
        rule.annual_consumption_value = annual_value
        rule.abc_class = abc
        rule.xyz_class = _xyz_class(s["cv"])
        rule.last_computed_at = now

        if rule.is_auto_calculated:
            lead = rule.lead_time_days or 7
            z = z_for_service_level(float(rule.service_level_percent))
            safety = int(math.ceil(z * s["std_dev"] * math.sqrt(lead)))
            lead_demand = int(math.ceil(s["avg_daily"] * lead))
            review_demand = int(math.ceil(s["avg_daily"] * (rule.review_period_days or 30)))
            rule.safety_stock = safety
            rule.reorder_point = lead_demand + safety
            rule.min_level = safety
            rule.max_level = lead_demand + review_demand + safety
            rule.par_level = rule.max_level
            rule.reorder_quantity = max(rule.max_level - rule.reorder_point, 0)
        rule.save()

    return {
        "organization": organization.id,
        "window_days": days,
        "products_analysed": len(abc_by_product),
        "rules_created": created,
        "rules_updated": updated,
        "annual_consumption_value": str(grand_total),
        "computed_at": now.isoformat(),
    }


def suggested_orders(organization: Organization) -> list[dict[str, Any]]:
    """Every product at or below its reorder point, with the quantity to buy.

    Free stock nets off what is already reserved for approved orders — reserved
    units are spoken for and must not be counted as cover.
    """
    on_hand = on_hand_map(organization)
    reserved_rows = (
        InventoryBatch.objects.filter(
            organization=organization, status=InventoryBatch.Status.ACTIVE
        )
        .values("product_id")
        .annotate(total=Sum("quantity_reserved"))
    )
    reserved = {r["product_id"]: int(r["total"] or 0) for r in reserved_rows}

    rules = (
        ReorderRule.objects.filter(organization=organization, is_active=True)
        .select_related("product", "preferred_supplier", "warehouse")
        .order_by("abc_class", "product__generic_name")
    )

    out: list[dict[str, Any]] = []
    for rule in rules:
        free = on_hand.get(rule.product_id, 0) - reserved.get(rule.product_id, 0)
        if rule.reorder_point <= 0 and rule.min_level <= 0:
            continue
        trigger = rule.reorder_point or rule.min_level
        if free > trigger:
            continue
        target = rule.max_level or rule.par_level or (trigger + rule.reorder_quantity)
        qty = max(target - free, rule.reorder_quantity, 1)
        daily = float(rule.avg_daily_demand)
        cover_days = round(free / daily, 1) if daily > 0 else None
        urgency = "CRITICAL" if free <= 0 else "HIGH" if free <= rule.safety_stock else "NORMAL"
        unit_cost = _unit_cost(organization, rule.product_id)
        out.append(
            {
                "product": rule.product_id,
                "product_name": f"{rule.product.generic_name} {rule.product.strength}".strip(),
                "abc_class": rule.abc_class,
                "xyz_class": rule.xyz_class,
                "free_stock": free,
                "on_hand": on_hand.get(rule.product_id, 0),
                "reserved": reserved.get(rule.product_id, 0),
                "reorder_point": rule.reorder_point,
                "safety_stock": rule.safety_stock,
                "max_level": rule.max_level,
                "suggested_quantity": int(qty),
                "avg_daily_demand": str(rule.avg_daily_demand),
                "days_of_cover": cover_days,
                "lead_time_days": rule.lead_time_days,
                "urgency": urgency,
                "unit_cost": str(unit_cost),
                "estimated_value": str((unit_cost * Decimal(int(qty))).quantize(Decimal("0.01"))),
                "preferred_supplier": rule.preferred_supplier_id,
                "preferred_supplier_name": (
                    rule.preferred_supplier.name if rule.preferred_supplier else None
                ),
            }
        )
    order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2}
    out.sort(key=lambda r: (order[r["urgency"]], r["abc_class"] or "Z"))
    return out


def abc_xyz_matrix(organization: Organization) -> dict[str, Any]:
    """The 3×3 ABC/XYZ grid — counts and stock value in each cell.

    AX (valuable and predictable) deserves tight automatic replenishment; CZ (cheap
    and erratic) deserves a big buffer and no attention.
    """
    on_hand = on_hand_map(organization)
    cells: dict[str, dict[str, Any]] = {
        f"{a}{x}": {"count": 0, "units": 0, "value": Decimal("0"), "products": []}
        for a in "ABC"
        for x in "XYZ"
    }
    rules = ReorderRule.objects.filter(organization=organization).select_related("product")
    unclassified = 0
    for rule in rules:
        key = f"{rule.abc_class}{rule.xyz_class}"
        if key not in cells:
            unclassified += 1
            continue
        units = on_hand.get(rule.product_id, 0)
        value = _unit_cost(organization, rule.product_id) * Decimal(units)
        cells[key]["count"] += 1
        cells[key]["units"] += units
        cells[key]["value"] += value
        cells[key]["products"].append(
            {
                "product": rule.product_id,
                "product_name": f"{rule.product.generic_name} {rule.product.strength}".strip(),
                "on_hand": units,
                "annual_consumption_value": str(rule.annual_consumption_value),
            }
        )
    return {
        "cells": {
            k: {
                "count": v["count"],
                "units": v["units"],
                "value": str(v["value"].quantize(Decimal("0.01"))),
                "products": sorted(
                    v["products"],
                    key=lambda p: Decimal(p["annual_consumption_value"]),
                    reverse=True,
                )[:25],
            }
            for k, v in cells.items()
        },
        "unclassified": unclassified,
        "total_products": rules.count(),
    }


def slow_and_dead_stock(
    organization: Organization, *, slow_days: int = 90, dead_days: int = 180
) -> list[dict[str, Any]]:
    """Batches whose product has not moved for a long time, with capital tied up.

    ``DEAD`` — nothing has left in ``dead_days``. ``SLOW`` — nothing in
    ``slow_days``. ``NEVER_MOVED`` — the product has never had a demand movement
    at this org, which is a different (and worse) conversation.
    """
    last_moved: dict[int, Any] = {}
    for product_id, occurred in (
        StockMovement.objects.filter(organization=organization, movement_type__in=DEMAND_TYPES)
        .order_by("product_id", "-occurred_at")
        .values_list("product_id", "occurred_at")
    ):
        last_moved.setdefault(product_id, occurred)

    today = timezone.localdate()
    rows: list[dict[str, Any]] = []
    batches = (
        InventoryBatch.objects.filter(organization=organization, quantity_available__gt=0)
        .select_related("product")
        .order_by("product__generic_name", "expiry_date")
    )
    for batch in batches:
        moved = last_moved.get(batch.product_id)
        if moved is None:
            age = (today - batch.created_at.date()).days
            category, idle = "NEVER_MOVED", age
        else:
            idle = (today - timezone.localtime(moved).date()).days
            if idle >= dead_days:
                category = "DEAD"
            elif idle >= slow_days:
                category = "SLOW"
            else:
                continue
        cost = batch.wholesale_cost or Decimal("0")
        rows.append(
            {
                "batch": batch.id,
                "product": batch.product_id,
                "product_name": f"{batch.product.generic_name} {batch.product.strength}".strip(),
                "batch_number": batch.batch_number,
                "quantity_available": batch.quantity_available,
                "expiry_date": batch.expiry_date.isoformat(),
                "days_idle": idle,
                "last_moved_on": timezone.localtime(moved).date().isoformat() if moved else None,
                "category": category,
                "unit_cost": str(cost),
                "capital_tied": str(
                    (cost * Decimal(batch.quantity_available)).quantize(Decimal("0.01"))
                ),
            }
        )
    rows.sort(key=lambda r: Decimal(r["capital_tied"]), reverse=True)
    return rows


def near_expiry_actions(
    organization: Organization, *, horizon_days: int = 180
) -> list[dict[str, Any]]:
    """Batches approaching expiry, each with the action that is still open to it.

    The action narrows as the clock runs: return to supplier while there is time to
    ship it back, then discount/push to a branch that is actually selling it, then
    quarantine, then write it off. ``sell_through_days`` compares the quantity on
    hand against observed demand — the honest test of whether it can clear in time.
    """
    stats = demand_statistics(organization, days=90)
    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)

    rows: list[dict[str, Any]] = []
    batches = (
        InventoryBatch.objects.filter(
            organization=organization,
            quantity_available__gt=0,
            expiry_date__lte=horizon,
        )
        .exclude(status=InventoryBatch.Status.RECALLED)
        .select_related("product")
        .order_by("expiry_date")
    )
    for batch in batches:
        days_left = (batch.expiry_date - today).days
        daily = stats.get(batch.product_id, {}).get("avg_daily", 0.0)
        sell_through = round(batch.quantity_available / daily, 1) if daily > 0 else None
        will_clear = sell_through is not None and sell_through <= days_left

        if days_left < 0:
            action, urgency = "WRITE_OFF", "EXPIRED"
        elif days_left <= 30:
            action, urgency = "QUARANTINE_AND_DISPOSE", "CRITICAL"
        elif days_left <= 90:
            action = "SELL_THROUGH" if will_clear else "DISCOUNT_OR_TRANSFER"
            urgency = "HIGH"
        else:
            action = "MONITOR" if will_clear else "RETURN_TO_SUPPLIER"
            urgency = "WATCH"

        cost = batch.wholesale_cost or Decimal("0")
        rows.append(
            {
                "batch": batch.id,
                "product": batch.product_id,
                "product_name": f"{batch.product.generic_name} {batch.product.strength}".strip(),
                "batch_number": batch.batch_number,
                "quantity_available": batch.quantity_available,
                "expiry_date": batch.expiry_date.isoformat(),
                "days_to_expiry": days_left,
                "status": batch.status,
                "avg_daily_demand": round(daily, 3),
                "sell_through_days": sell_through,
                "will_clear_before_expiry": will_clear,
                "recommended_action": action,
                "urgency": urgency,
                "unit_cost": str(cost),
                "value_at_risk": str(
                    (cost * Decimal(batch.quantity_available)).quantize(Decimal("0.01"))
                ),
            }
        )
    return rows


# --- Cold chain ------------------------------------------------------------

# Arrhenius activation energy used by ICH/USP <1079> for MKT, in J/mol, and the
# universal gas constant in J/(mol·K).
_ACTIVATION_ENERGY = 83_144.0
_GAS_CONSTANT = 8.3144


def mean_kinetic_temperature(temperatures_celsius: list[float]) -> float | None:
    """Mean kinetic temperature (°C) for a series of readings.

    MKT is *not* the arithmetic mean: it is the single temperature that would
    produce the same cumulative degradation as the observed profile, so a short
    hot spike weighs far more than the same number of cold minutes. Formula per
    USP <1079> / ICH Q1A, assuming evenly-spaced readings.
    """
    kelvins = [t + 273.15 for t in temperatures_celsius if t is not None]
    kelvins = [k for k in kelvins if k > 0]
    if not kelvins:
        return None
    ratio = _ACTIVATION_ENERGY / _GAS_CONSTANT
    total = sum(math.exp(-ratio / k) for k in kelvins)
    if total <= 0:
        return None
    mkt_kelvin = ratio / -math.log(total / len(kelvins))
    return round(mkt_kelvin - 273.15, 3)


def sensor_thermal_profile(sensor: Any, *, start: Any = None, end: Any = None) -> dict[str, Any]:
    """MKT plus min/mean/max and excursion counts for one sensor over a window."""
    logs = TemperatureLog.objects.filter(sensor=sensor)
    if start:
        logs = logs.filter(recorded_at__gte=start)
    if end:
        logs = logs.filter(recorded_at__lte=end)

    temps = [float(t) for t in logs.values_list("temperature_celsius", flat=True)]
    zone = sensor.zone
    in_range = [
        t for t in temps if float(zone.temp_min_celsius) <= t <= float(zone.temp_max_celsius)
    ]
    breaches = logs.filter(
        Q(excursion_status=TemperatureLog.ExcursionStatus.CRITICAL_BREACH)
        | Q(excursion_status=TemperatureLog.ExcursionStatus.WARNING)
    ).count()

    return {
        "sensor": sensor.id,
        "sensor_name": sensor.name,
        "zone": zone.id,
        "zone_name": zone.name,
        "readings": len(temps),
        "min_celsius": round(min(temps), 2) if temps else None,
        "max_celsius": round(max(temps), 2) if temps else None,
        "mean_celsius": round(sum(temps) / len(temps), 2) if temps else None,
        "mkt_celsius": mean_kinetic_temperature(temps),
        "zone_min_celsius": str(zone.temp_min_celsius),
        "zone_max_celsius": str(zone.temp_max_celsius),
        "mkt_within_range": (
            None
            if not temps
            else float(zone.temp_min_celsius)
            <= (mean_kinetic_temperature(temps) or 0)
            <= float(zone.temp_max_celsius)
        ),
        "time_in_range_percent": (round(len(in_range) / len(temps) * 100, 2) if temps else None),
        "excursion_readings": breaches,
        "calibration_state": sensor.calibration_state,
        "calibration_due_date": (
            sensor.calibration_due_date.isoformat() if sensor.calibration_due_date else None
        ),
        "window_start": start.isoformat() if start else None,
        "window_end": end.isoformat() if end else None,
    }
