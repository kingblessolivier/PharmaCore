"""Warehouse execution & ownership services.

Three write-paths that the flat ``services.py`` deliberately does not carry,
because each keeps its own invariants:

* **Put-away** — turn a received lot into a concrete bin, by policy.
* **Wave picking** — build FEFO pick tasks from demand, release them to the floor,
  confirm picks, and short-pick honestly when the bin is empty.
* **Consignment / VMI** — record consumption of stock somebody else owns, and roll
  a period's consumptions into a settlement (an AP bill for supplier-owned stock).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.iam.models import Organization, User
from apps.inventory.models import (
    BinLocation,
    ConsignmentAgreement,
    ConsignmentConsumption,
    ConsignmentSettlement,
    InventoryBatch,
    PickTask,
    PickWave,
    PutawayRule,
    StockMovement,
    StorageZone,
    Warehouse,
)

# Product storage conditions that demand a cold-chain zone.
_COLD_CONDITIONS = ("COLD_CHAIN", "REFRIGERATED", "FROZEN", "2-8", "COLD")


# --- Put-away --------------------------------------------------------------


def _zone_type_for_product(product: Any) -> str:
    """The zone a product's label conditions require, before any rule is applied."""
    condition = (getattr(product, "storage_condition", "") or "").upper()
    if getattr(product, "is_controlled_substance", False):
        return StorageZone.ZoneType.CONTROLLED_SAFE
    if "FREEZ" in condition or "-20" in condition:
        return StorageZone.ZoneType.FREEZER
    if any(token in condition for token in _COLD_CONDITIONS):
        return StorageZone.ZoneType.COLD_CHAIN
    max_temp = getattr(product, "max_temp_c", None)
    if max_temp is not None and float(max_temp) <= 8:
        return StorageZone.ZoneType.COLD_CHAIN
    return StorageZone.ZoneType.AMBIENT


def _rule_matches(rule: PutawayRule, product: Any, abc_class: str) -> bool:
    if rule.match_product_id and rule.match_product_id != product.pk:
        return False
    if rule.match_controlled_only and not getattr(product, "is_controlled_substance", False):
        return False
    if rule.match_cold_chain_only and _zone_type_for_product(product) not in (
        StorageZone.ZoneType.COLD_CHAIN,
        StorageZone.ZoneType.FREEZER,
    ):
        return False
    if rule.match_abc_class and rule.match_abc_class != abc_class:
        return False
    # Named rather than inlined into `return not (...)`: every criterion above is a
    # guard clause, and collapsing only the last one would break that symmetry.
    zone_mismatch = rule.match_zone_type and rule.match_zone_type != _zone_type_for_product(product)
    return not zone_mismatch


def _first_free_bin(zone: StorageZone) -> BinLocation | None:
    return zone.bins.filter(is_occupied=False).order_by("aisle", "shelf", "bin_code").first()


def suggest_putaway(
    *,
    organization: Organization,
    product: Any,
    warehouse: Warehouse | None = None,
    quantity: int = 0,
) -> dict[str, Any]:
    """Decide where a received lot should go, and say why.

    Rules are evaluated in ``priority`` order and the first match wins. When no
    rule matches we still answer — falling back to the zone the product's own
    storage condition requires, because a cold-chain product must never be
    defaulted onto an ambient shelf just because nobody wrote a rule.
    """
    required_zone_type = _zone_type_for_product(product)
    abc_class = ""
    rule_qs = PutawayRule.objects.filter(organization=organization, is_active=True)
    if warehouse is not None:
        rule_qs = rule_qs.filter(Q(warehouse=warehouse) | Q(warehouse__isnull=True))
    from apps.inventory.models import ReorderRule

    rule_row = ReorderRule.objects.filter(organization=organization, product=product).first()
    if rule_row:
        abc_class = rule_row.abc_class

    for rule in rule_qs.select_related("target_zone", "target_bin").order_by("priority", "id"):
        if not _rule_matches(rule, product, abc_class):
            continue

        if rule.strategy == PutawayRule.Strategy.FIXED_BIN and rule.target_bin is not None:
            return _putaway_result(
                rule,
                rule.target_bin.zone,
                rule.target_bin,
                required_zone_type,
                quantity,
                "Fixed slot on the matching rule.",
            )

        zone = rule.target_zone
        if zone is None:
            zone = _pick_zone(organization, warehouse, required_zone_type)
        if zone is None:
            continue

        if rule.strategy == PutawayRule.Strategy.ABC_VELOCITY:
            # Fast movers go to the lowest aisle/shelf — nearest the dispatch door.
            bin_location = (
                zone.bins.filter(is_occupied=False).order_by("aisle", "shelf", "bin_code").first()
                if abc_class == "A"
                else zone.bins.filter(is_occupied=False).order_by("-aisle", "-shelf").first()
            )
            why = f"ABC velocity: class {abc_class or '—'} placement."
        elif rule.strategy == PutawayRule.Strategy.BULK_THEN_PICK:
            bin_location = zone.bins.filter(
                is_occupied=False, shelf__iexact="BULK"
            ).first() or _first_free_bin(zone)
            why = "Bulk slot first, overflow to the pick face."
        else:
            bin_location = _first_free_bin(zone)
            why = (
                "Zone matched to the product's storage condition."
                if rule.strategy == PutawayRule.Strategy.ZONE_BY_CONDITION
                else "Nearest empty bin in the target zone."
            )
        return _putaway_result(rule, zone, bin_location, required_zone_type, quantity, why)

    zone = _pick_zone(organization, warehouse, required_zone_type)
    return _putaway_result(
        None,
        zone,
        _first_free_bin(zone) if zone else None,
        required_zone_type,
        quantity,
        "No rule matched — defaulted to the zone this product's storage condition requires.",
    )


def _pick_zone(
    organization: Organization, warehouse: Warehouse | None, zone_type: str
) -> StorageZone | None:
    qs = StorageZone.objects.filter(organization=organization, is_active=True)
    if warehouse is not None:
        qs = qs.filter(Q(warehouse=warehouse) | Q(warehouse__isnull=True))
    return qs.filter(zone_type=zone_type).order_by("name").first()


def _putaway_result(
    rule: PutawayRule | None,
    zone: StorageZone | None,
    bin_location: BinLocation | None,
    required_zone_type: str,
    quantity: int,
    why: str,
) -> dict[str, Any]:
    compliant = zone is not None and zone.zone_type == required_zone_type
    return {
        "rule": rule.id if rule else None,
        "rule_name": rule.name if rule else None,
        "strategy": rule.strategy if rule else "DEFAULT_BY_CONDITION",
        "zone": zone.id if zone else None,
        "zone_name": zone.name if zone else None,
        "zone_type": zone.zone_type if zone else None,
        "bin_location": bin_location.id if bin_location else None,
        "bin_code": bin_location.bin_code if bin_location else None,
        "required_zone_type": required_zone_type,
        "storage_compliant": compliant,
        "quantity": quantity,
        "reason": why,
        "warning": (
            None
            if compliant
            else f"No free {required_zone_type} location available — do not put this stock away "
            "until one is cleared."
        ),
    }


@transaction.atomic
def apply_putaway(
    *, batch: InventoryBatch, bin_location: BinLocation, user: User | None = None
) -> InventoryBatch:
    """Commit a put-away: move the lot into the bin and mark the bin occupied."""
    previous = batch.bin_location
    batch.bin_location = bin_location
    batch.storage_location = bin_location.bin_code
    if bin_location.zone.warehouse_id:
        batch.warehouse_id = bin_location.zone.warehouse_id
    batch.save(update_fields=["bin_location", "storage_location", "warehouse", "updated_at"])

    bin_location.is_occupied = True
    bin_location.save(update_fields=["is_occupied"])
    if previous and previous.pk != bin_location.pk and not previous.batches.exists():
        previous.is_occupied = False
        previous.save(update_fields=["is_occupied"])
    return batch


# --- Wave picking ----------------------------------------------------------


def _bin_sort_key(task_bin: BinLocation | None) -> tuple[str, str, str]:
    if task_bin is None:
        return ("~", "~", "~")
    return (task_bin.aisle or "~", task_bin.shelf or "~", task_bin.bin_code)


@transaction.atomic
def build_pick_tasks(
    *,
    wave: PickWave,
    demands: list[dict[str, Any]],
    user: User | None = None,
) -> list[PickTask]:
    """Turn demand lines into FEFO pick tasks, walk-ordered.

    ``demands`` is ``[{"product": Product, "quantity": int, "reference_type": str,
    "reference_id": str}]``. Each demand is split across as many batches as it takes,
    soonest-expiry first, skipping expired and non-ACTIVE lots. A demand that cannot
    be fully covered still produces tasks for what *is* there plus one ``SHORT`` task
    for the gap — the floor needs to see the shortfall, not a silently smaller number.
    """
    if wave.status != PickWave.Status.DRAFT:
        raise ValueError("Pick tasks can only be built while the wave is a draft.")

    built: list[PickTask] = []
    for demand in demands:
        product = demand["product"]
        remaining = int(demand["quantity"])
        if remaining <= 0:
            continue
        batches = (
            InventoryBatch.objects.select_for_update()
            .filter(
                organization=wave.organization,
                product=product,
                status=InventoryBatch.Status.ACTIVE,
                expiry_date__gte=date.today(),
                quantity_available__gt=0,
            )
            .select_related("bin_location", "bin_location__zone")
            .order_by("expiry_date", "batch_number")
        )
        if wave.warehouse_id:
            batches = batches.filter(Q(warehouse_id=wave.warehouse_id) | Q(warehouse__isnull=True))
        if wave.zone_id:
            batches = batches.filter(bin_location__zone_id=wave.zone_id)

        for batch in batches:
            if remaining <= 0:
                break
            free = batch.quantity_available - batch.quantity_reserved
            take = min(remaining, max(free, 0))
            if take <= 0:
                continue
            built.append(
                PickTask(
                    wave=wave,
                    product=product,
                    batch=batch,
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date,
                    zone=batch.bin_location.zone if batch.bin_location else None,
                    bin_location=batch.bin_location,
                    quantity_requested=take,
                    reference_type=demand.get("reference_type", ""),
                    reference_id=str(demand.get("reference_id", "")),
                )
            )
            remaining -= take

        if remaining > 0:
            built.append(
                PickTask(
                    wave=wave,
                    product=product,
                    quantity_requested=remaining,
                    status=PickTask.Status.SHORT,
                    short_reason="No sellable batch available at wave build time.",
                    reference_type=demand.get("reference_type", ""),
                    reference_id=str(demand.get("reference_id", "")),
                )
            )

    # Walk order. BATCH/CLUSTER waves group the same product together so the picker
    # takes it once; ZONE and the rest walk the racking in aisle/shelf/bin order.
    if wave.strategy in (PickWave.Strategy.BATCH, PickWave.Strategy.CLUSTER):
        built.sort(key=lambda t: (t.product_id, _bin_sort_key(t.bin_location)))
    else:
        built.sort(
            key=lambda t: (
                t.zone.name if t.zone else "~",
                *_bin_sort_key(t.bin_location),
                t.expiry_date or date.max,
            )
        )
    for index, task in enumerate(built, start=1):
        task.sequence = index

    PickTask.objects.bulk_create(built)
    return list(wave.tasks.select_related("product", "batch", "zone", "bin_location").all())


@transaction.atomic
def release_wave(*, wave: PickWave, user: User | None = None) -> PickWave:
    """Release a wave to the floor, reserving every task's stock as it goes.

    Reserving at release is what stops two waves promising the same units: the
    reservation is visible to FEFO allocation everywhere else in the system.
    """
    if wave.status != PickWave.Status.DRAFT:
        raise ValueError("Only a draft wave can be released.")
    if not wave.tasks.exists():
        raise ValueError("Build pick tasks before releasing the wave.")

    for task in wave.tasks.select_for_update().select_related("batch"):
        batch = task.batch
        if task.status != PickTask.Status.PENDING or batch is None:
            continue
        free = batch.quantity_available - batch.quantity_reserved
        if free < task.quantity_requested:
            task.status = PickTask.Status.SHORT
            task.short_reason = (
                f"Only {max(free, 0)} free at release; {task.quantity_requested} required."
            )
            task.save(update_fields=["status", "short_reason"])
            continue
        batch.quantity_reserved += task.quantity_requested
        batch.save(update_fields=["quantity_reserved", "updated_at"])
        task.status = PickTask.Status.ASSIGNED
        task.picker = wave.assigned_to or user
        task.save(update_fields=["status", "picker"])

    wave.status = PickWave.Status.RELEASED
    wave.released_at = timezone.now()
    wave.save(update_fields=["status", "released_at"])
    return wave


@transaction.atomic
def confirm_pick(
    *, task: PickTask, quantity_picked: int, user: User | None = None, short_reason: str = ""
) -> PickTask:
    """Confirm what actually came off the shelf and release the reservation.

    A short pick is recorded as short, not rounded away: the unpicked reservation is
    freed so the stock returns to general availability rather than staying invisibly
    committed to a wave that has moved on.
    """
    if task.status in (PickTask.Status.PICKED, PickTask.Status.CANCELLED):
        raise ValueError("This pick task is already closed.")
    if quantity_picked < 0:
        raise ValueError("Picked quantity cannot be negative.")
    if quantity_picked > task.quantity_requested:
        raise ValueError("Cannot pick more than the task requested.")

    if task.batch_id:
        batch = InventoryBatch.objects.select_for_update().get(pk=task.batch_id)
        batch.quantity_reserved = max(0, batch.quantity_reserved - task.quantity_requested)
        if quantity_picked:
            batch.quantity_reserved += quantity_picked
        batch.save(update_fields=["quantity_reserved", "updated_at"])

    task.quantity_picked = quantity_picked
    task.picker = user or task.picker
    task.picked_at = timezone.now()
    task.status = (
        PickTask.Status.PICKED
        if quantity_picked == task.quantity_requested
        else PickTask.Status.SHORT
    )
    if task.status == PickTask.Status.SHORT:
        task.short_reason = short_reason or "Short picked at the bin."
    task.save(update_fields=["quantity_picked", "picker", "picked_at", "status", "short_reason"])

    wave = task.wave
    open_tasks = wave.tasks.filter(
        status__in=[PickTask.Status.PENDING, PickTask.Status.ASSIGNED]
    ).exists()
    wave.status = PickWave.Status.PICKING if open_tasks else PickWave.Status.PICKED
    wave.completed_at = None if open_tasks else timezone.now()
    wave.save(update_fields=["status", "completed_at"])
    return task


@transaction.atomic
def cancel_wave(*, wave: PickWave, user: User | None = None) -> PickWave:
    """Cancel a wave and hand every un-picked reservation back to free stock."""
    if wave.status in (PickWave.Status.PICKED, PickWave.Status.CANCELLED):
        raise ValueError("A completed or cancelled wave cannot be cancelled again.")
    for task in wave.tasks.select_for_update().select_related("batch"):
        batch = task.batch
        if task.status == PickTask.Status.ASSIGNED and batch is not None:
            batch.quantity_reserved = max(0, batch.quantity_reserved - task.quantity_requested)
            batch.save(update_fields=["quantity_reserved", "updated_at"])
        if task.status != PickTask.Status.PICKED:
            task.status = PickTask.Status.CANCELLED
            task.save(update_fields=["status"])
    wave.status = PickWave.Status.CANCELLED
    wave.completed_at = timezone.now()
    wave.save(update_fields=["status", "completed_at"])
    return wave


# --- Consignment / VMI -----------------------------------------------------


def record_consignment_consumption(
    *,
    batch: InventoryBatch,
    quantity: int,
    trigger: str,
    movement: StockMovement | None = None,
) -> ConsignmentConsumption | None:
    """Log consumption of consigned stock — the event that creates the liability.

    A no-op for owned stock, so call sites can invoke it unconditionally after any
    draw-down. Title on consigned stock passes at consumption, which is exactly the
    moment this row is written.
    """
    agreement = batch.consignment_agreement
    if not batch.is_consignment or agreement is None:
        return None
    if quantity <= 0:
        return None
    if agreement.status != ConsignmentAgreement.Status.ACTIVE:
        return None

    unit_cost = batch.wholesale_cost or Decimal("0")
    return ConsignmentConsumption.objects.create(
        agreement=agreement,
        batch=batch,
        product=batch.product,
        batch_number=batch.batch_number,
        quantity=quantity,
        unit_cost=unit_cost,
        total_value=(unit_cost * Decimal(quantity)).quantize(Decimal("0.01")),
        movement=movement,
        trigger=trigger,
    )


@transaction.atomic
def settle_consignment(
    *,
    agreement: ConsignmentAgreement,
    settlement_no: str,
    period_start: date,
    period_end: date,
    raise_bill: bool = True,
    user: User | None = None,
) -> ConsignmentSettlement:
    """Roll a period's unsettled consumptions into one settlement.

    For ``SUPPLIER_OWNED`` stock this is where we finally owe the supplier: a
    ``SupplierBill`` is raised for the consumed value and posted to the GL, which is
    the whole economic point of consignment — you pay for what you used, when you
    used it.
    """
    consumptions = ConsignmentConsumption.objects.select_for_update().filter(
        agreement=agreement,
        settlement__isnull=True,
        consumed_at__date__gte=period_start,
        consumed_at__date__lte=period_end,
    )
    total_qty = sum(c.quantity for c in consumptions)
    total_value = sum((c.total_value for c in consumptions), Decimal("0"))
    lines = consumptions.count()
    if lines == 0:
        raise ValueError("No unsettled consumption in that period.")

    settlement = ConsignmentSettlement.objects.create(
        agreement=agreement,
        settlement_no=settlement_no,
        period_start=period_start,
        period_end=period_end,
        total_quantity=total_qty,
        total_value=total_value,
        lines_count=lines,
        created_by=user,
    )
    consumptions.update(settlement=settlement)

    if (
        raise_bill
        and agreement.direction == ConsignmentAgreement.Direction.SUPPLIER_OWNED
        and agreement.owner_supplier_id
        and total_value > 0
    ):
        from datetime import timedelta

        from apps.finance.services import record_supplier_bill

        bill = record_supplier_bill(
            organization=agreement.organization,
            supplier=agreement.owner_supplier,
            bill_number=f"CONS-{settlement_no}",
            bill_date=period_end,
            due_date=period_end + timedelta(days=agreement.payment_terms_days or 30),
            total_amount=total_value,
            reference_type="consignment_settlement",
            reference_id=str(settlement.pk),
            notes=(
                f"Consignment settlement {settlement_no} for agreement "
                f"{agreement.agreement_no}: {lines} consumption line(s), {total_qty} unit(s)."
            ),
            user=user,
        )
        settlement.supplier_bill = bill
        settlement.status = ConsignmentSettlement.Status.INVOICED
        settlement.settled_at = timezone.now()
        settlement.save(update_fields=["supplier_bill", "status", "settled_at"])
    return settlement


def consignment_position(agreement: ConsignmentAgreement) -> dict[str, Any]:
    """On-hand-but-not-ours (or ours-but-not-here) plus the unsettled liability."""
    batches = agreement.batches.select_related("product").filter(quantity_available__gt=0)
    on_hand_units = sum(b.quantity_available for b in batches)
    on_hand_value = sum(
        ((b.wholesale_cost or Decimal("0")) * Decimal(b.quantity_available) for b in batches),
        Decimal("0"),
    )
    unsettled = agreement.consumptions.filter(settlement__isnull=True)
    unsettled_value = sum((c.total_value for c in unsettled), Decimal("0"))
    return {
        "agreement": agreement.id,
        "agreement_no": agreement.agreement_no,
        "direction": agreement.direction,
        "counterparty": agreement.counterparty_name,
        "batches_held": batches.count(),
        "units_held": on_hand_units,
        "value_held": str(on_hand_value.quantize(Decimal("0.01"))),
        "unsettled_lines": unsettled.count(),
        "unsettled_units": sum(c.quantity for c in unsettled),
        "unsettled_value": str(unsettled_value.quantize(Decimal("0.01"))),
        "settlements": agreement.settlements.count(),
        "credit_limit": str(agreement.credit_limit) if agreement.credit_limit else None,
        "over_credit_limit": bool(
            agreement.credit_limit and unsettled_value > agreement.credit_limit
        ),
    }
