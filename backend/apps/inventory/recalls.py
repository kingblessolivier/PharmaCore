"""Batch recalls: freeze what is still held, and find what already left.

A recall is not a freeze. Freezing on-hand stock catches the units that did not
move — which are, by definition, the ones that reached nobody. The units that
matter are the ones already sitting on a pharmacy shelf or inside a patient's
cupboard, and finding those is the whole exercise.

Everything needed to trace them is already recorded:

    InventoryBatch        what is still held, and where
    InTransitStock        what left a depot and has not arrived
    ShipmentItem/GRNLine  which pharmacy received it, on which delivery
    SaleBatchAllocation   which sale drew on it -> which patient was dispensed it

The other half of a recall is scope. ``batch_number`` is unique only within
``(organization, product)``, so two manufacturers can and do ship different
medicines under the same batch string. A recall keyed on the string alone
quarantines unrelated stock, which is both a patient-safety event of its own
(medicine withdrawn for no reason) and a commercial loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.iam.audit import record_audit
from apps.inventory.models import BatchRecall, InventoryBatch

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User


class RecallError(ValueError):
    """A recall cannot proceed as asked."""


@dataclass
class Holder:
    """One organization still holding, or having received, recalled stock."""

    organization_id: int
    organization_name: str
    on_hand_units: int = 0
    in_transit_units: int = 0
    received_units: int = 0
    dispensed_units: int = 0

    @property
    def total_units(self) -> int:
        return self.on_hand_units + self.in_transit_units + self.received_units


@dataclass
class Trace:
    """Where every unit of a recalled batch went."""

    product_id: int
    product_name: str
    batch_number: str
    holders: list[Holder] = field(default_factory=list)
    patients: list[dict[str, Any]] = field(default_factory=list)

    @property
    def units_still_held(self) -> int:
        return sum(h.on_hand_units for h in self.holders)

    @property
    def units_in_transit(self) -> int:
        return sum(h.in_transit_units for h in self.holders)

    @property
    def units_dispensed(self) -> int:
        return sum(int(p["quantity"]) for p in self.patients)

    @property
    def reached_patients(self) -> bool:
        return bool(self.patients)


def trace_batch(*, product: Any, batch_number: str) -> Trace:
    """Follow one batch of one product everywhere it went.

    Scoped to ``(product, batch_number)`` deliberately — see the module docstring.
    """
    from apps.distribution.models import GRNLine, InTransitStock
    from apps.retail.models import SaleBatchAllocation

    product_id = getattr(product, "pk", product)
    holders: dict[int, Holder] = {}

    def holder(org_id: int, name: str) -> Holder:
        if org_id not in holders:
            holders[org_id] = Holder(organization_id=org_id, organization_name=name)
        return holders[org_id]

    batches = InventoryBatch.objects.filter(
        product_id=product_id, batch_number=batch_number
    ).select_related("organization", "product")
    product_name = ""
    for batch in batches:
        product_name = product_name or str(batch.product)
        holder(
            batch.organization_id, batch.organization.name
        ).on_hand_units += batch.quantity_available

    for row in InTransitStock.objects.filter(
        product_id=product_id, batch_number=batch_number
    ).select_related("destination_org"):
        holder(row.destination_org_id, row.destination_org.name).in_transit_units += row.quantity

    for line in GRNLine.objects.filter(
        product_id=product_id, batch_number=batch_number
    ).select_related("grn__retail"):
        org = line.grn.retail
        holder(org.pk, org.name).received_units += line.quantity_received

    # The last link: which patients were handed this batch. A dispensing record
    # exists only where one was legally required, so a sale without one still
    # counts as dispensed — it just cannot be attributed to a named person.
    patients: list[dict[str, Any]] = []
    allocations = (
        SaleBatchAllocation.objects.filter(
            batch__product_id=product_id, batch__batch_number=batch_number
        )
        .select_related("sale_item__sale__dispensing", "sale_item__sale__organization")
        .order_by("-sale_item__sale__created_at")
    )
    for alloc in allocations:
        sale = alloc.sale_item.sale
        dispensing = getattr(sale, "dispensing", None)
        org = sale.organization
        holder(org.pk, org.name).dispensed_units += alloc.quantity
        patients.append(
            {
                "sale": sale.pk,
                "sale_number": sale.sale_number,
                "organization": org.pk,
                "organization_name": org.name,
                "quantity": alloc.quantity,
                "sold_at": sale.created_at,
                "patient_name": dispensing.patient_name if dispensing else "",
                "patient_id_number": dispensing.patient_id_number if dispensing else "",
                "prescriber_name": dispensing.prescriber_name if dispensing else "",
                "contactable": bool(dispensing and dispensing.patient_name),
            }
        )
        if not product_name:
            product_name = str(alloc.batch.product)

    if not product_name:
        from apps.catalog.models import Product

        found = Product.objects.filter(pk=product_id).first()
        product_name = str(found) if found else f"Product {product_id}"

    return Trace(
        product_id=int(product_id),
        product_name=product_name,
        batch_number=batch_number,
        holders=sorted(holders.values(), key=lambda h: -h.total_units),
        patients=patients,
    )


@transaction.atomic
def freeze(*, recall: BatchRecall, user: User | None = None) -> Trace:
    """Quarantine every unit of the recalled batch that is still on a shelf.

    Scoped to the recall's own product. Filtering on ``batch_number`` alone — as
    this did — withdraws unrelated medicines from sale wherever a manufacturer
    happens to have reused the batch string.
    """
    if recall.status == BatchRecall.Status.COMPLETED:
        raise RecallError("This recall is already closed.")

    affected = InventoryBatch.objects.filter(
        product_id=recall.product_id, batch_number=recall.batch_number
    ).exclude(status=InventoryBatch.Status.RECALLED)
    frozen = affected.update(status=InventoryBatch.Status.RECALLED)

    trace = trace_batch(product=recall.product_id, batch_number=recall.batch_number)

    recall.status = BatchRecall.Status.IN_PROGRESS
    recall.save(update_fields=["status"])

    record_audit(
        action="RECALL_FROZEN",
        user=user,
        organization=None,
        entity_type="batch_recall",
        entity_id=str(recall.pk),
        changes={
            "product": trace.product_name,
            "batch_number": recall.batch_number,
            "batches_frozen": frozen,
            "units_still_held": trace.units_still_held,
            "units_in_transit": trace.units_in_transit,
            "units_dispensed": trace.units_dispensed,
            "organizations_affected": len(trace.holders),
            "reached_patients": trace.reached_patients,
        },
    )
    return trace


@transaction.atomic
def close(*, recall: BatchRecall, user: User | None = None) -> BatchRecall:
    """Close a recall once every frozen unit has been accounted for.

    Refused while recalled stock is still on hand: the point of a recall is that
    the units are physically dealt with, and closing it early loses the only
    record of which ones were not.
    """
    if recall.status == BatchRecall.Status.COMPLETED:
        raise RecallError("This recall is already closed.")

    remaining = (
        InventoryBatch.objects.filter(
            product_id=recall.product_id,
            batch_number=recall.batch_number,
            status=InventoryBatch.Status.RECALLED,
        )
        .filter(quantity_available__gt=0)
        .count()
    )
    if remaining:
        raise RecallError(
            f"{remaining} recalled batch(es) still hold stock. Dispose of them first — "
            "closing now would leave those units unaccounted for."
        )

    recall.status = BatchRecall.Status.COMPLETED
    recall.save(update_fields=["status"])
    record_audit(
        action="RECALL_CLOSED",
        user=user,
        organization=None,
        entity_type="batch_recall",
        entity_id=str(recall.pk),
        changes={"batch_number": recall.batch_number},
    )
    return recall


def summary(*, organization: Any) -> dict[str, Any]:
    """Recall exposure for the inventory overview."""
    org_id = getattr(organization, "pk", organization)
    open_recalls = BatchRecall.objects.exclude(status=BatchRecall.Status.COMPLETED)
    held = InventoryBatch.objects.filter(
        organization_id=org_id, status=InventoryBatch.Status.RECALLED, quantity_available__gt=0
    )
    return {
        "open_recalls": open_recalls.count(),
        "recalled_batches_held": held.count(),
        "recalled_units_held": sum(b.quantity_available for b in held),
    }
