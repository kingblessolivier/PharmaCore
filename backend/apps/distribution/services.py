"""Distribution services: depot approval + FEFO stock allocation (reservation).

Approving a pending order reserves depot stock against it, soonest-expiring first
(FEFO). Reservations hold stock (batch.quantity_reserved) without moving it —
actual deduction (TRANSFER_OUT) happens at dispatch (a later slice). Cancelling
releases the holds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction

from apps.distribution.models import OrderItem, Reservation, Shipment, StockOrder
from apps.iam.models import User
from apps.inventory.models import InventoryBatch, StockMovement


@dataclass
class ItemAllocation:
    order_item: OrderItem
    approved: int
    reserved: int  # how much stock we could actually hold (≤ approved)


def _reserve_item(item: OrderItem, depot_id: int, user: User | None) -> ItemAllocation:
    """Reserve up to the approved quantity from the depot's FEFO batches."""
    remaining = item.quantity_approved
    batches = (
        InventoryBatch.objects.select_for_update()
        .filter(
            organization_id=depot_id,
            product=item.product,
            status=InventoryBatch.Status.ACTIVE,
        )
        .order_by("expiry_date", "batch_number")  # FEFO
    )
    reserved = 0
    for batch in batches:
        if remaining <= 0:
            break
        free = batch.quantity_available - batch.quantity_reserved
        if free <= 0:
            continue
        take = min(remaining, free)
        Reservation.objects.create(order=item.order, order_item=item, batch=batch, quantity=take)
        batch.quantity_reserved += take
        batch.save(update_fields=["quantity_reserved", "updated_at"])
        remaining -= take
        reserved += take
    return ItemAllocation(order_item=item, approved=item.quantity_approved, reserved=reserved)


@transaction.atomic
def approve_and_allocate(*, order: StockOrder, user: User | None) -> list[ItemAllocation]:
    """Approve a pending order (approved qty = ordered qty) and FEFO-reserve depot stock.

    Reservation may be partial when depot stock is short — the order is still approved;
    the shortfall surfaces at picking/dispatch. Returns per-line allocation.
    """
    allocations: list[ItemAllocation] = []
    for item in order.items.select_related("product").all():
        item.quantity_approved = item.quantity_ordered
        item.save(update_fields=["quantity_approved"])
        allocations.append(_reserve_item(item, order.depot_id, user))

    order.status = StockOrder.Status.APPROVED
    order.approved_by = user
    order.save(update_fields=["status", "approved_by", "updated_at"])
    return allocations


@transaction.atomic
def release_order_reservations(*, order: StockOrder) -> None:
    """Release every hold this order placed (e.g. on cancel)."""
    for res in order.reservations.select_related("batch").select_for_update():
        batch = res.batch
        batch.quantity_reserved = max(0, batch.quantity_reserved - res.quantity)
        batch.save(update_fields=["quantity_reserved", "updated_at"])
        res.delete()


@transaction.atomic
def dispatch_order(
    *, order: StockOrder, driver_name: str, vehicle_registration: str, user: User | None
) -> Shipment:
    """Dispatch a picked order: consume its reservations, deduct depot stock via
    TRANSFER_OUT ledger movements, record shipped quantities, and create a shipment."""
    shipped: dict[int, int] = defaultdict(int)
    for res in order.reservations.select_related("batch", "order_item").select_for_update():
        batch = res.batch
        # Reserved stock physically leaves the depot: reduce both counters.
        batch.quantity_available -= res.quantity
        batch.quantity_reserved = max(0, batch.quantity_reserved - res.quantity)
        batch.save(update_fields=["quantity_available", "quantity_reserved", "updated_at"])
        StockMovement.objects.create(
            organization=order.depot,
            product=res.order_item.product,
            batch=batch,
            batch_number=batch.batch_number,
            movement_type=StockMovement.Type.TRANSFER_OUT,
            quantity_delta=-res.quantity,
            reference_type="shipment",
            reference_id=str(order.pk),
            created_by=user,
        )
        shipped[res.order_item_id] += res.quantity
        res.delete()

    for item in order.items.all():
        item.quantity_shipped = shipped.get(item.pk, 0)
        item.save(update_fields=["quantity_shipped"])

    shipment = Shipment.objects.create(
        order=order,
        driver_name=driver_name,
        vehicle_registration=vehicle_registration,
        dispatched_by=user,
    )
    order.status = StockOrder.Status.IN_TRANSIT
    order.save(update_fields=["status", "updated_at"])
    return shipment
