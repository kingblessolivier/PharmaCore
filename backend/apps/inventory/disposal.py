"""Witnessed destruction of stock that must never be sold.

Three things have to happen together, and previously none of them did — the
endpoint set a status and a timestamp:

1. **The units leave stock.** Until they do, expired or recalled medicine is
   still counted as sellable and FEFO will happily allocate it to a patient.
2. **A movement is written.** The stock ledger has to explain every change in
   on-hand, and "it went down because someone destroyed it" is the explanation.
3. **The loss reaches the P&L.** Stock written off is an expense. Leaving it out
   flatters margin by exactly the value of the medicine thrown away.

Destruction is also irreversible, so it is guarded: only quarantined, recalled or
expired stock can be destroyed, both witnesses must be recorded, and confirming
twice cannot remove the same units twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.iam.audit import record_audit
from apps.inventory.models import DisposalLine, InventoryBatch, StockDisposal, StockMovement

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User


class DisposalError(ValueError):
    """A destruction cannot proceed as asked."""


#: Only stock already withdrawn from sale may be destroyed. Destroying ACTIVE
#: stock would mean the decision to withdraw it was never recorded anywhere.
_DESTROYABLE = (
    InventoryBatch.Status.QUARANTINE,
    InventoryBatch.Status.RECALLED,
    InventoryBatch.Status.EXPIRED,
)


@dataclass
class DestructionOutcome:
    """What a confirmed destruction removed and what it cost."""

    disposal: StockDisposal
    units_destroyed: int
    value_written_off: Decimal
    lines: int


@transaction.atomic
def add_line(
    *, disposal: StockDisposal, batch: InventoryBatch, quantity: int, note: str = ""
) -> DisposalLine:
    """Put a batch on a disposal, with the quantity to be destroyed."""
    if disposal.status == StockDisposal.Status.DESTROYED:
        raise DisposalError("This disposal has already been carried out.")
    if quantity <= 0:
        raise DisposalError("A disposal line needs a positive quantity.")
    if batch.organization_id != disposal.organization_id:
        raise DisposalError(
            f"Batch {batch.batch_number} belongs to another organization — "
            "stock can only be destroyed by whoever holds it."
        )
    if quantity > batch.quantity_available:
        raise DisposalError(
            f"Batch {batch.batch_number} holds {batch.quantity_available} unit(s); "
            f"cannot destroy {quantity}."
        )
    line, created = DisposalLine.objects.get_or_create(
        disposal=disposal,
        batch=batch,
        defaults={"quantity": quantity, "note": note[:255]},
    )
    if not created:
        line.quantity = quantity
        line.note = note[:255]
        line.save(update_fields=["quantity", "note"])
    return line


@transaction.atomic
def confirm_destruction(*, disposal: StockDisposal, user: User | None = None) -> DestructionOutcome:
    """Destroy the listed stock: remove it, record it, and write it off.

    Idempotent per line — a line that already carries ``destroyed_quantity`` is
    skipped, so a retry or a double-click cannot remove the same units twice.
    """
    from apps.finance.services import post_inventory_adjustment

    disposal = StockDisposal.objects.select_for_update().get(pk=disposal.pk)
    if disposal.status == StockDisposal.Status.DESTROYED:
        raise DisposalError("This disposal has already been carried out.")

    lines = list(
        DisposalLine.objects.select_for_update()
        .filter(disposal=disposal)
        .select_related("batch", "batch__product")
    )
    if not lines:
        raise DisposalError(
            "Nothing is listed for destruction — add the batches being destroyed first."
        )
    if not disposal.secondary_witness_name.strip():
        raise DisposalError(
            "A second witness must be named. Destruction is witnessed by two people, "
            "and one of them cannot be a blank field."
        )

    units = 0
    value = Decimal("0.00")

    for line in lines:
        if line.is_destroyed:
            continue
        batch = line.batch
        if batch.status not in _DESTROYABLE:
            raise DisposalError(
                f"Batch {batch.batch_number} is {batch.get_status_display().lower()} — "
                "withdraw it from sale before destroying it, so the decision is on record."
            )
        if line.quantity > batch.quantity_available:
            raise DisposalError(
                f"Batch {batch.batch_number} now holds {batch.quantity_available} unit(s); "
                f"the disposal lists {line.quantity}. Recount before destroying."
            )

        batch.quantity_available -= line.quantity
        batch.save(update_fields=["quantity_available", "updated_at"])

        StockMovement.objects.create(
            organization=disposal.organization,
            product=batch.product,
            batch=batch,
            batch_number=batch.batch_number,
            movement_type=StockMovement.Type.WASTAGE,
            quantity_delta=-line.quantity,
            reference_type="stock_disposal",
            reference_id=str(disposal.pk),
            created_by=user,
        )

        unit_cost = batch.wholesale_cost or Decimal("0")
        value += (unit_cost * line.quantity).quantize(Decimal("0.01"))
        units += line.quantity

        # Negative delta: the goods are gone, so the loss is an expense.
        post_inventory_adjustment(
            batch=batch,
            delta=-line.quantity,
            unit_cost=batch.wholesale_cost,
            reason=(
                f"Witnessed destruction {disposal.disposal_no} "
                f"({disposal.get_reason_display()})"
            ),
            reference_type="stock_disposal",
            reference_id=f"{disposal.pk}:{line.pk}",
            user=user,
        )

        line.destroyed_quantity = line.quantity
        line.save(update_fields=["destroyed_quantity"])

    disposal.status = StockDisposal.Status.DESTROYED
    disposal.destroyed_at = timezone.now()
    disposal.save(update_fields=["status", "destroyed_at"])

    record_audit(
        action="STOCK_DESTROYED",
        user=user,
        organization=disposal.organization,
        entity_type="stock_disposal",
        entity_id=str(disposal.pk),
        changes={
            "disposal_no": disposal.disposal_no,
            "reason": disposal.reason,
            "units": units,
            "value": str(value),
            "witnesses": [
                disposal.primary_witness.get_full_name() or disposal.primary_witness.username,
                disposal.secondary_witness_name,
            ],
            "certificate_no": disposal.certificate_no,
        },
    )
    return DestructionOutcome(
        disposal=disposal, units_destroyed=units, value_written_off=value, lines=len(lines)
    )


def destruction_candidates(*, organization: Any) -> list[dict[str, Any]]:
    """Stock that cannot be sold and is waiting to be destroyed.

    Expired stock that is still marked ACTIVE is included: it is unsellable in
    fact even where nobody has changed its status, and it is the most common
    thing to be sitting unnoticed on a shelf.
    """
    org_id = getattr(organization, "pk", organization)
    today = timezone.localdate()
    rows: list[dict[str, Any]] = []
    batches = (
        InventoryBatch.objects.filter(organization_id=org_id, quantity_available__gt=0)
        .filter(status__in=_DESTROYABLE + (InventoryBatch.Status.ACTIVE,))
        .select_related("product")
        .order_by("expiry_date")
    )
    for batch in batches:
        expired = batch.expiry_date < today
        if batch.status == InventoryBatch.Status.ACTIVE and not expired:
            continue
        rows.append(
            {
                "batch": batch.pk,
                "batch_number": batch.batch_number,
                "product": batch.product_id,
                "product_name": str(batch.product),
                "quantity": batch.quantity_available,
                "expiry_date": batch.expiry_date,
                "status": batch.status,
                "is_expired": expired,
                "value": str(
                    ((batch.wholesale_cost or Decimal("0")) * batch.quantity_available).quantize(
                        Decimal("0.01")
                    )
                ),
                "reason": (
                    StockDisposal.Reason.RECALLED
                    if batch.status == InventoryBatch.Status.RECALLED
                    else StockDisposal.Reason.EXPIRED if expired else StockDisposal.Reason.DAMAGED
                ),
            }
        )
    return rows


def summary(*, organization: Any) -> dict[str, Any]:
    """Destruction backlog for the inventory overview."""
    candidates = destruction_candidates(organization=organization)
    org_id = getattr(organization, "pk", organization)
    return {
        "awaiting_destruction": len(candidates),
        "units_awaiting": sum(int(c["quantity"]) for c in candidates),
        "value_awaiting": str(sum(Decimal(str(c["value"])) for c in candidates)),
        "expired_still_active": sum(
            1 for c in candidates if c["is_expired"] and c["status"] == InventoryBatch.Status.ACTIVE
        ),
        "destroyed_this_period": StockDisposal.objects.filter(
            organization_id=org_id, status=StockDisposal.Status.DESTROYED
        ).count(),
    }
