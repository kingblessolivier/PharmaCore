"""Distribution services: depot approval + FEFO stock allocation (reservation).

Approving a pending order reserves depot stock against it, soonest-expiring first
(FEFO). Reservations hold stock (batch.quantity_reserved) without moving it —
actual deduction (TRANSFER_OUT) happens at dispatch (a later slice). Cancelling
releases the holds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.distribution.models import (
    GoodsReceivedNote,
    GRNLine,
    InTransitStock,
    OrderItem,
    OrderPayment,
    Reservation,
    Shipment,
    ShipmentItem,
    StockOrder,
)
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.iam.models import User
from apps.inventory.models import InventoryBatch, StockMovement
from apps.inventory.services import receive_intake


def _product_label(product: object) -> str:
    return f"{product.generic_name} {product.strength}".strip()  # type: ignore[attr-defined]


def generate_po_document(*, order: StockOrder, user: User | None) -> Document:
    lines = [
        {
            "name": _product_label(i.product),
            "qty": i.quantity_ordered,
            "price": i.price_per_unit,
            "total": i.line_total,
        }
        for i in order.items.select_related("product").all()
    ]
    return generate_document(
        organization=order.retail,
        doc_type=DocType.PURCHASE_ORDER,
        context={
            "buyer_name": order.retail.name,
            "seller_name": order.depot.name,
            "lines": lines,
            "total": order.total_amount,
        },
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


def _generate_delivery_note(order: StockOrder, shipment: Shipment, user: User | None) -> None:
    lines = [
        {
            "name": _product_label(si.product),
            "batch": si.batch_number,
            "expiry": si.expiry_date,
            "qty": si.quantity,
        }
        for si in shipment.items.select_related("product").all()
    ]
    generate_document(
        organization=order.depot,
        doc_type=DocType.DELIVERY_NOTE,
        context={
            "from_name": order.depot.name,
            "to_name": order.retail.name,
            "driver": shipment.driver_name,
            "vehicle": shipment.vehicle_registration,
            "lines": lines,
        },
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


def _generate_grn_and_invoice(grn: GoodsReceivedNote, user: User | None) -> None:
    order = grn.order
    generate_document(
        organization=grn.retail,
        doc_type=DocType.GRN,
        context={
            "retail_name": grn.retail.name,
            "depot_name": order.depot.name,
            "has_discrepancy": grn.has_discrepancy,
            "lines": [
                {
                    "name": _product_label(line.product),
                    "batch": line.batch_number,
                    "expiry": line.expiry_date,
                    "expected": line.quantity_expected,
                    "received": line.quantity_received,
                    "damaged": line.quantity_damaged,
                }
                for line in grn.lines.select_related("product").all()
            ],
        },
        reference_type="grn",
        reference_id=str(grn.pk),
        user=user,
    )
    generate_document(
        organization=order.depot,
        doc_type=DocType.TAX_INVOICE,
        context={
            "seller_name": order.depot.name,
            "buyer_name": order.retail.name,
            "total": order.total_amount,
            "lines": [
                {
                    "name": _product_label(i.product),
                    "tax_class": i.product.tax_class,
                    "qty": i.quantity_shipped or i.quantity_ordered,
                    "price": i.price_per_unit,
                    "total": i.line_total,
                }
                for i in order.items.select_related("product").all()
            ],
        },
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


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
    TRANSFER_OUT ledger movements, record the packing manifest, and create a shipment."""
    shipment = Shipment.objects.create(
        order=order,
        driver_name=driver_name,
        vehicle_registration=vehicle_registration,
        dispatched_by=user,
    )
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
        ShipmentItem.objects.create(
            shipment=shipment,
            order_item=res.order_item,
            product=res.order_item.product,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            quantity=res.quantity,
        )
        # Hold the units in the in-transit ledger until the pharmacy receives them.
        InTransitStock.objects.create(
            order=order,
            source_org=order.depot,
            destination_org=order.retail,
            product=res.order_item.product,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            quantity=res.quantity,
            driver_name=driver_name,
            vehicle_plate=vehicle_registration,
        )
        shipped[res.order_item_id] += res.quantity
        res.delete()

    for item in order.items.all():
        item.quantity_shipped = shipped.get(item.pk, 0)
        item.save(update_fields=["quantity_shipped"])

    order.status = StockOrder.Status.IN_TRANSIT
    order.save(update_fields=["status", "updated_at"])
    _generate_delivery_note(order, shipment, user)
    return shipment


@transaction.atomic
def record_order_payment(
    *, order: StockOrder, amount: Any, method: str, reference: str, user: User | None
) -> StockOrder:
    """Record a payment the pharmacy made to the wholesaler and roll up the order's
    settlement status (UNPAID → PARTIAL → PAID)."""
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Payment amount must be positive.")
    OrderPayment.objects.create(
        order=order, amount=amt, method=method, reference=reference, recorded_by=user
    )
    order.amount_paid = order.amount_paid + amt
    total = Decimal(str(order.total_amount))
    if order.amount_paid >= total:
        order.payment_status = StockOrder.PaymentStatus.PAID
    elif order.amount_paid > 0:
        order.payment_status = StockOrder.PaymentStatus.PARTIAL
    order.save(update_fields=["amount_paid", "payment_status", "updated_at"])
    return order


@transaction.atomic
def approve_and_ship(*, order: StockOrder, user: User | None) -> StockOrder:
    """Lean approval: the depot approves and the stock leaves in one step.

    FEFO-reserves the depot's batches then immediately dispatches them (deducting
    depot stock via TRANSFER_OUT and recording the batch manifest), so the order
    goes straight from PENDING to IN_TRANSIT. No separate picking/driver step.
    """
    approve_and_allocate(order=order, user=user)
    dispatch_order(order=order, driver_name="", vehicle_registration="", user=user)
    order.refresh_from_db()
    return order


@transaction.atomic
def receive_all(*, order: StockOrder, user: User | None) -> StockOrder:
    """Lean reception: the pharmacy confirms the goods arrived in one click.

    Opens a GRN pre-filled from the manifest and finalizes it as fully received —
    landing the stock in the pharmacy's inventory (TRANSFER_IN, which also lists
    the product in its catalog). No per-item counting.
    """
    grn = open_grn(order=order, user=user)
    finalize_grn(grn=grn, lines_data={}, user=user)
    order.refresh_from_db()
    return order


@transaction.atomic
def open_grn(*, order: StockOrder, user: User | None) -> GoodsReceivedNote:
    """Open a GRN for an in-transit order, pre-filled from the shipment manifest."""
    shipment = order.shipments.order_by("-dispatched_at").first()
    grn = GoodsReceivedNote.objects.create(
        order=order, shipment=shipment, retail=order.retail, received_by=user
    )
    grn.grn_number = f"GRN-{grn.pk:05d}"
    grn.save(update_fields=["grn_number"])
    if shipment is not None:
        for si in shipment.items.select_related("order_item", "product").all():
            GRNLine.objects.create(
                grn=grn,
                order_item=si.order_item,
                product=si.product,
                batch_number=si.batch_number,
                expiry_date=si.expiry_date,
                quantity_expected=si.quantity,
                quantity_received=si.quantity,  # default: received all
            )
    return grn


@transaction.atomic
def finalize_grn(
    *, grn: GoodsReceivedNote, lines_data: dict[int, dict[str, Any]], user: User | None
) -> GoodsReceivedNote:
    """Finalize a GRN: write good stock into retail inventory (TRANSFER_IN), record
    discrepancies, and move the order to DELIVERED / PARTIALLY_RECEIVED."""
    received_per_item: dict[int, int] = defaultdict(int)
    any_discrepancy = False
    for line in grn.lines.select_related("order_item", "product").all():
        data = lines_data.get(line.pk, {})
        line.quantity_received = int(data.get("quantity_received", line.quantity_received))
        line.quantity_damaged = int(data.get("quantity_damaged", 0))
        line.save(update_fields=["quantity_received", "quantity_damaged"])

        good = max(0, line.quantity_received - line.quantity_damaged)
        if good > 0:
            receive_intake(
                organization=grn.retail,
                product=line.product,
                batch_number=line.batch_number,
                expiry_date=line.expiry_date,
                quantity=good,
                user=user,
                movement_type=StockMovement.Type.TRANSFER_IN,
                reference_type="grn",
                reference_id=str(grn.pk),
                source_org=grn.order.depot,  # recall traceability: which depot it came from
            )
        received_per_item[line.order_item_id] += line.quantity_received
        any_discrepancy = any_discrepancy or line.has_discrepancy

    order = grn.order
    fully_received = True
    for item in order.items.all():
        item.quantity_received = received_per_item.get(item.pk, 0)
        item.save(update_fields=["quantity_received"])
        if item.quantity_received < item.quantity_shipped:
            fully_received = False

    order.status = (
        StockOrder.Status.DELIVERED if fully_received else StockOrder.Status.PARTIALLY_RECEIVED
    )
    order.save(update_fields=["status", "updated_at"])

    grn.status = GoodsReceivedNote.Status.FINALIZED
    grn.has_discrepancy = any_discrepancy
    grn.save(update_fields=["status", "has_discrepancy"])
    # The goods have arrived — clear them from the in-transit ledger.
    order.in_transit.all().delete()
    _generate_grn_and_invoice(grn, user)
    return grn
