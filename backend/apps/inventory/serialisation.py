"""Per-unit serialisation & track-&-trace write-path.

Scanning a DataMatrix is only useful if the scan *changes state and leaves a
record*. Every function here does both: it moves the :class:`SerialUnit` and
writes the matching immutable :class:`EpcisEvent`, so the unit's history and the
EPCIS export are the same data rather than two things that can drift apart.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.iam.models import Organization, User
from apps.inventory import gs1
from apps.inventory.models import EpcisEvent, InventoryBatch, SerialUnit

# Which disposition each business step leaves the unit in (CBV pairings).
_STEP_DISPOSITION = {
    EpcisEvent.BizStep.COMMISSIONING: EpcisEvent.Disposition.ACTIVE,
    EpcisEvent.BizStep.PACKING: EpcisEvent.Disposition.IN_PROGRESS,
    EpcisEvent.BizStep.UNPACKING: EpcisEvent.Disposition.IN_PROGRESS,
    EpcisEvent.BizStep.RECEIVING: EpcisEvent.Disposition.SELLABLE_ACCESSIBLE,
    EpcisEvent.BizStep.SHIPPING: EpcisEvent.Disposition.IN_TRANSIT,
    EpcisEvent.BizStep.DISPENSING: EpcisEvent.Disposition.RETAIL_SOLD,
    EpcisEvent.BizStep.DESTROYING: EpcisEvent.Disposition.DESTROYED,
    EpcisEvent.BizStep.HOLDING: EpcisEvent.Disposition.RECALLED,
    EpcisEvent.BizStep.STORING: EpcisEvent.Disposition.SELLABLE_ACCESSIBLE,
    EpcisEvent.BizStep.INSPECTING: EpcisEvent.Disposition.IN_PROGRESS,
}

# The status a unit lands in after each step.
_STEP_STATUS = {
    EpcisEvent.BizStep.COMMISSIONING: SerialUnit.Status.COMMISSIONED,
    EpcisEvent.BizStep.RECEIVING: SerialUnit.Status.IN_STOCK,
    EpcisEvent.BizStep.STORING: SerialUnit.Status.IN_STOCK,
    EpcisEvent.BizStep.SHIPPING: SerialUnit.Status.IN_TRANSIT,
    EpcisEvent.BizStep.DISPENSING: SerialUnit.Status.DISPENSED,
    EpcisEvent.BizStep.DESTROYING: SerialUnit.Status.DESTROYED,
    EpcisEvent.BizStep.HOLDING: SerialUnit.Status.RECALLED,
}


def record_event(
    *,
    organization: Organization,
    event_type: str,
    action: str,
    biz_step: str = "",
    disposition: str = "",
    epcs: list[str] | None = None,
    parent_epc: str = "",
    read_point: str = "",
    biz_location: str = "",
    reference_type: str = "",
    reference_id: str = "",
    user: User | None = None,
    event_time: Any = None,
) -> EpcisEvent:
    """Append one EPCIS event. Never updated, never deleted — that is the point."""
    return EpcisEvent.objects.create(
        organization=organization,
        event_id=gs1.new_event_id(),
        event_type=event_type,
        action=action,
        biz_step=biz_step,
        disposition=disposition or _STEP_DISPOSITION.get(biz_step, ""),
        epc_list=epcs or [],
        parent_epc=parent_epc,
        read_point=read_point or organization.name,
        biz_location=biz_location or organization.name,
        reference_type=reference_type,
        reference_id=reference_id,
        event_time=event_time or timezone.now(),
        created_by=user,
    )


@transaction.atomic
def commission_from_scan(
    *,
    organization: Organization,
    scan: str,
    product: Any = None,
    batch: InventoryBatch | None = None,
    user: User | None = None,
    read_point: str = "",
) -> tuple[SerialUnit, dict[str, Any], bool]:
    """Parse a scanned DataMatrix and register (or re-find) the unit it identifies.

    Returns ``(unit, parsed, created)``. Re-scanning a code returns the existing
    unit instead of raising: a second scan at goods-in is an ordinary event, and
    the caller gets ``created=False`` so it can tell the difference.
    """
    parsed = gs1.parse_gs1(scan)
    gtin = parsed.get("gtin", "")
    serial = parsed.get("serial", "")
    sscc = parsed.get("sscc", "")
    if not (serial or sscc):
        raise ValueError(
            "This code carries no serial (AI 21) or SSCC (AI 00) — it identifies a "
            "product, not an individual unit, so it cannot be serialised."
        )

    lookup = (
        {"organization": organization, "sscc": sscc}
        if sscc
        else {"organization": organization, "gtin": gtin, "serial": serial}
    )
    existing = SerialUnit.objects.filter(**lookup).first()
    if existing:
        existing.last_scanned_at = timezone.now()
        existing.save(update_fields=["last_scanned_at", "updated_at"])
        return existing, parsed, False

    # Resolve the product from the GTIN when the caller did not name one.
    if product is None and gtin:
        from apps.catalog.models import Product

        product = Product.objects.filter(gtin=gtin.lstrip("0")).first() or Product.objects.filter(
            gtin=gtin
        ).first()

    # ``parse_gs1`` hands dates back as ISO strings; the model wants a real date so
    # everything downstream (``trace``, expiry maths) gets a date, not a string.
    expiry = parsed.get("expiry_date")
    if isinstance(expiry, str):
        expiry = date.fromisoformat(expiry)

    batch_number = parsed.get("batch_number", "")
    if batch is None and product is not None and batch_number:
        batch = InventoryBatch.objects.filter(
            organization=organization, product=product, batch_number=batch_number
        ).first()

    unit = SerialUnit.objects.create(
        organization=organization,
        product=product,
        batch=batch,
        level=SerialUnit.Level.PALLET if sscc else SerialUnit.Level.EACH,
        gtin=gtin,
        serial=serial,
        sscc=sscc,
        epc=parsed.get("epc", ""),
        batch_number=batch_number or (batch.batch_number if batch else ""),
        expiry_date=expiry or (batch.expiry_date if batch else None),
        status=SerialUnit.Status.COMMISSIONED,
        last_scanned_at=timezone.now(),
    )
    record_event(
        organization=organization,
        event_type=EpcisEvent.EventType.OBJECT,
        action=EpcisEvent.Action.ADD,
        biz_step=EpcisEvent.BizStep.COMMISSIONING,
        epcs=[unit.epc] if unit.epc else [],
        read_point=read_point,
        user=user,
    )
    return unit, parsed, True


@transaction.atomic
def aggregate(
    *, parent: SerialUnit, children: list[SerialUnit], user: User | None = None
) -> SerialUnit:
    """Pack children into a parent (each → case → pallet) and log the AggregationEvent.

    Aggregation only goes up the hierarchy: a case cannot contain a pallet, and a
    unit cannot be packed into itself or into something it already contains.
    """
    order = {SerialUnit.Level.EACH: 0, SerialUnit.Level.CASE: 1, SerialUnit.Level.PALLET: 2}
    for child in children:
        if child.pk == parent.pk:
            raise ValueError("A unit cannot contain itself.")
        if order[child.level] >= order[parent.level]:
            raise ValueError(
                f"Cannot pack a {child.level} into a {parent.level} — aggregation only "
                "goes each → case → pallet."
            )
        if child.organization_id != parent.organization_id:
            raise ValueError("Cannot aggregate units belonging to different organizations.")

    ids = [c.pk for c in children]
    SerialUnit.objects.filter(pk__in=ids).update(parent=parent, updated_at=timezone.now())
    parent.quantity = sum(
        (c.quantity for c in SerialUnit.objects.filter(parent=parent)), 0
    )
    parent.save(update_fields=["quantity", "updated_at"])

    record_event(
        organization=parent.organization,
        event_type=EpcisEvent.EventType.AGGREGATION,
        action=EpcisEvent.Action.ADD,
        biz_step=EpcisEvent.BizStep.PACKING,
        epcs=[c.epc for c in children if c.epc],
        parent_epc=parent.epc,
        user=user,
    )
    return parent


@transaction.atomic
def disaggregate(
    *, parent: SerialUnit, children: list[SerialUnit] | None = None, user: User | None = None
) -> SerialUnit:
    """Unpack — all children, or only the named ones."""
    qs = SerialUnit.objects.filter(parent=parent)
    if children is not None:
        qs = qs.filter(pk__in=[c.pk for c in children])
    epcs = [e for e in qs.values_list("epc", flat=True) if e]
    qs.update(parent=None, updated_at=timezone.now())
    remaining = sum((c.quantity for c in SerialUnit.objects.filter(parent=parent)), 0)
    # An each is always one unit of itself; a case/pallet holds whatever is left.
    parent.quantity = 1 if parent.level == SerialUnit.Level.EACH else remaining
    parent.save(update_fields=["quantity", "updated_at"])

    record_event(
        organization=parent.organization,
        event_type=EpcisEvent.EventType.AGGREGATION,
        action=EpcisEvent.Action.DELETE,
        biz_step=EpcisEvent.BizStep.UNPACKING,
        epcs=epcs,
        parent_epc=parent.epc,
        user=user,
    )
    return parent


def _descendants(unit: SerialUnit) -> list[SerialUnit]:
    """Every unit under this one, at any depth (pallet → cases → eaches)."""
    out: list[SerialUnit] = []
    frontier = list(unit.children.all())
    while frontier:
        node = frontier.pop()
        out.append(node)
        frontier.extend(node.children.all())
    return out


@transaction.atomic
def observe(
    *,
    units: list[SerialUnit],
    biz_step: str,
    user: User | None = None,
    read_point: str = "",
    reference_type: str = "",
    reference_id: str = "",
    cascade: bool = True,
) -> list[SerialUnit]:
    """Record a business step against units — shipping, receiving, dispensing…

    ``cascade`` carries the step down the aggregation tree, which is what makes a
    single pallet scan at dispatch move all 1 200 packs on it.
    """
    targets: dict[int, SerialUnit] = {u.pk: u for u in units}
    if cascade:
        for unit in units:
            for child in _descendants(unit):
                targets[child.pk] = child

    ids = list(targets)
    new_status = _STEP_STATUS.get(biz_step)
    if new_status:
        SerialUnit.objects.filter(pk__in=ids).update(
            status=new_status, last_scanned_at=timezone.now(), updated_at=timezone.now()
        )
    else:
        SerialUnit.objects.filter(pk__in=ids).update(last_scanned_at=timezone.now())

    org = units[0].organization if units else None
    if org is not None:
        record_event(
            organization=org,
            event_type=EpcisEvent.EventType.OBJECT,
            action=EpcisEvent.Action.OBSERVE,
            biz_step=biz_step,
            epcs=[u.epc for u in targets.values() if u.epc],
            read_point=read_point,
            reference_type=reference_type,
            reference_id=reference_id,
            user=user,
        )
    return list(SerialUnit.objects.filter(pk__in=targets))


def trace(unit: SerialUnit) -> dict[str, Any]:
    """The full chain-of-custody for one unit: identity, parents, children, events."""
    ancestry: list[dict[str, Any]] = []
    node = unit.parent
    seen: set[int] = set()
    while node is not None and node.pk not in seen:
        seen.add(node.pk)
        ancestry.append({"id": node.pk, "level": node.level, "epc": node.epc, "sscc": node.sscc})
        node = node.parent

    # ``epc_list`` is a JSON array and the ``contains`` lookup is unsupported on
    # SQLite, so the membership test is done in Python over a bounded recent window
    # rather than with a backend-specific query that would work only in production.
    events: list[EpcisEvent] = []
    if unit.epc:
        recent = EpcisEvent.objects.filter(organization=unit.organization).order_by(
            "-event_time", "-id"
        )[:2000]
        events = [
            e for e in recent if unit.epc in (e.epc_list or []) or e.parent_epc == unit.epc
        ]
        # Tie-break on the insertion order: two scans can land in the same clock
        # tick, and a custody trail that reports them out of order is worse than
        # useless — it is evidence of something that did not happen.
        events.sort(key=lambda e: (e.event_time, e.pk))

    return {
        "unit": unit.pk,
        "epc": unit.epc,
        "gtin": unit.gtin,
        "serial": unit.serial,
        "sscc": unit.sscc,
        "level": unit.level,
        "status": unit.status,
        "batch_number": unit.batch_number,
        "expiry_date": unit.expiry_date.isoformat() if unit.expiry_date else None,
        "product_name": (
            f"{unit.product.generic_name} {unit.product.strength}".strip()
            if unit.product_id
            else None
        ),
        "packed_into": ancestry,
        "contains": [
            {"id": c.pk, "level": c.level, "epc": c.epc, "status": c.status}
            for c in _descendants(unit)
        ],
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "action": e.action,
                "biz_step": e.biz_step,
                "disposition": e.disposition,
                "event_time": e.event_time.isoformat(),
                "read_point": e.read_point,
            }
            for e in events
        ],
    }
