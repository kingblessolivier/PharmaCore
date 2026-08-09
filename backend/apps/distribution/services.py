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
from django.utils import timezone

from apps.catalog.models import Product
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
from apps.documents import invoicing
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.iam.models import User
from apps.inventory.models import InventoryBatch, StockMovement
from apps.inventory.services import receive_intake


def _product_label(product: object) -> str:
    return f"{product.generic_name} {product.strength}".strip()  # type: ignore[attr-defined]


def _base_unit_label(product: Any) -> str:
    """What this medicine is ultimately counted in — tablets, vials, bottles."""
    base = next((u for u in product.units.all() if u.is_base), None)
    if base is None:
        return "units"
    return base.name or base.get_code_display()


def generate_po_document(*, order: StockOrder, user: User | None) -> Document:
    # The unit travels with the quantity. A depot reading "10" cannot tell ten
    # cartons from ten tablets, and picking the wrong one is an error of
    # whatever the carton holds.
    lines = [
        {
            # A code the depot can quote back. Without one every line on a
            # wholesale order printed "—" in the Item # column.
            "item_number": (i.product.rra_item_code or i.product.gtin or f"P{i.product_id}"),
            "name": _product_label(i.product),
            "qty": i.quantity_ordered,
            # A line ordered in base units still has a unit — it is the base
            # one. Printing "—" told the depot nothing about what to pick.
            "unit_label": i.unit_label or _base_unit_label(i.product),
            "base_quantity": i.quantity_base or i.quantity_ordered,
            "base_unit": _base_unit_label(i.product),
            "price": invoicing.money(i.price_per_ordered_unit),
            "total": invoicing.money(i.line_total),
        }
        for i in order.items.select_related("product", "unit").all()
    ]
    # Every figure the form has a row for, formatted, and never a bare float.
    # This context used to carry `total` alone — so a B2B order printed with
    # Subtotal, Tax, Shipping and Other blank and a total reading "7500.0".
    # The template is shared with procurement's purchase order; a shared
    # template needs the whole context, not the part one caller happens to use.
    buyer = invoicing.party(order.retail)
    seller = invoicing.party(order.depot)
    net = Decimal(str(order.total_amount))
    return generate_document(
        organization=order.retail,
        doc_type=DocType.PURCHASE_ORDER,
        context={
            "buyer_name": buyer["name"],
            "buyer_phone": buyer.get("phone", ""),
            "deliver_to_address": buyer.get("address", ""),
            "seller_name": seller["name"],
            "seller_address": seller.get("address", ""),
            "seller_phone": seller.get("phone", ""),
            "seller_tin": seller.get("tin", ""),
            "lines": lines,
            "subtotal": invoicing.money(net),
            "tax_total": invoicing.money(0),
            "freight_amount": invoicing.money(0),
            "other_charges": invoicing.money(0),
            "discount_amount": invoicing.money(0),
            "total": invoicing.money(net),
            "amount_in_words": invoicing.in_words(net, currency=order.retail.currency or "RWF"),
            "po_number": order.order_number,
            "order_date": order.created_at,
            "expected_delivery": order.expected_delivery,
            "payment_terms_days": None,
            "notes": order.notes,
            "currency": order.retail.currency,
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
            # A line shipped in base units still has a unit — the base one.
            # Printing "—" on a delivery note tells the driver and the
            # storekeeper nothing about what they are counting.
            "unit_label": (
                (si.order_item.unit_label if si.order_item_id else "")
                or _base_unit_label(si.product)
            ),
            "base_quantity": si.quantity,
            "base_unit": _base_unit_label(si.product),
        }
        for si in shipment.items.select_related("product", "order_item", "order_item__unit").all()
    ]
    consignor = invoicing.party(order.depot)
    consignee = invoicing.party(order.retail)
    # A cold-chain consignment has to be labelled as one on the paperwork that
    # travels with it, because the person who decides whether to put it in a
    # cold box is reading this, not the catalogue.
    cold_chain = any(
        si.product.storage_condition in (Product.Storage.COLD_CHAIN, Product.Storage.FROZEN)
        for si in shipment.items.select_related("product").all()
    )
    generate_document(
        organization=order.depot,
        doc_type=DocType.DELIVERY_NOTE,
        context={
            "from_name": consignor["name"],
            "from_address": consignor.get("address", ""),
            "from_phone": consignor.get("phone", ""),
            "to_name": consignee["name"],
            "to_address": consignee.get("address", ""),
            "to_phone": consignee.get("phone", ""),
            "driver": shipment.driver_name,
            "vehicle": shipment.vehicle_registration,
            "dispatched_at": shipment.dispatched_at,
            "order_number": order.order_number,
            "packages": len(lines),
            "cold_chain": cold_chain,
            "lines": lines,
        },
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


def _generate_grn_and_invoice(grn: GoodsReceivedNote, user: User | None) -> None:
    order = grn.order
    # A goods receipt is the moment custody passes, so the document has to
    # carry who it came from, what it was ordered against, and — because this
    # is medicine — the batch and expiry of every line. Without those a recall
    # cannot be traced back through it.
    supplier = invoicing.party(order.depot)
    shipment = grn.shipment
    grn_lines = []
    receipt_value = Decimal("0")
    for line in grn.lines.select_related("product", "order_item", "order_item__unit").all():
        item = line.order_item
        unit_label = item.unit_label if item else ""
        price = Decimal(str(item.price_per_unit)) if item else Decimal("0")
        value = price * Decimal(str(line.quantity_received))
        receipt_value += value
        grn_lines.append(
            {
                "name": _product_label(line.product),
                "batch": line.batch_number,
                "expiry": line.expiry_date,
                "unit_label": unit_label,
                "base_quantity": line.quantity_received,
                "base_unit": _base_unit_label(line.product),
                "expected": line.quantity_expected,
                "received": line.quantity_received,
                "damaged": line.quantity_damaged,
                "value": invoicing.money(value),
            }
        )

    generate_document(
        organization=grn.retail,
        doc_type=DocType.GRN,
        context={
            "grn_number": grn.grn_number,
            "retail_name": grn.retail.name,
            "depot_name": order.depot.name,
            "supplier_name": supplier["name"],
            "supplier_address": supplier.get("address", ""),
            "supplier_phone": supplier.get("phone", ""),
            "supplier_tin": supplier.get("tin", ""),
            "order_number": order.order_number,
            "received_at": grn.received_at,
            "has_discrepancy": grn.has_discrepancy,
            # Named on the document rather than left blank: the two signatures
            # are what make a later dispute about a short delivery answerable,
            # and whoever signs should be the person the system already knows
            # handed over and accepted.
            "delivered_by_name": shipment.driver_name if shipment else "",
            "delivered_on": shipment.dispatched_at if shipment else None,
            "received_by_name": (
                grn.received_by.get_full_name() or grn.received_by.username
                if grn.received_by
                else ""
            ),
            "show_values": True,
            "total": invoicing.money(receipt_value),
            "currency": grn.retail.currency or "RWF",
            "lines": grn_lines,
        },
        reference_type="grn",
        reference_id=str(grn.pk),
        user=user,
    )
    # Built through the shared assembler so this invoice and the one finance
    # raises say the same things in the same places — they were building
    # different context dictionaries for the same template.
    invoice_lines = []
    net_total = Decimal("0")
    vat_total = Decimal("0")
    for i in order.items.select_related("product", "unit").all():
        rate = invoicing.TAX_CLASS_RATES.get(str(i.product.tax_class).upper(), Decimal("0"))
        net = Decimal(str(i.line_total))
        vat = (net * rate / 100).quantize(Decimal("0.01"))
        net_total += net
        vat_total += vat
        invoice_lines.append(
            {
                "name": _product_label(i.product),
                "tax_class": i.product.tax_class,
                "tax_rate": rate,
                "tax_amount": vat,
                "net": net,
                "qty": i.quantity_shipped or i.quantity_ordered,
                "unit_label": i.unit_label,
                "base_quantity": i.quantity_base or i.quantity_ordered,
                "base_unit": _base_unit_label(i.product),
                "price": invoicing.money(i.price_per_ordered_unit),
                "total": invoicing.money(net),
            }
        )

    generate_document(
        organization=order.depot,
        doc_type=DocType.TAX_INVOICE,
        context=invoicing.invoice_context(
            seller=order.depot,
            buyer=order.retail,
            lines=invoice_lines,
            subtotal=net_total,
            tax_total=vat_total,
            total=net_total + vat_total,
            currency=order.depot.currency or "RWF",
            invoice_number=order.order_number,
            invoice_date=order.created_at,
            due_date=order.payment_due_date,
            payment_terms=(
                f"{order.payment_due_date:%d %b %Y}" if order.payment_due_date else "On delivery"
            ),
            # Balance due, not just the total. A customer paying in stages
            # needs the invoice to say what is still owed on it, and a single
            # "total" answers a different question.
            amount_paid=invoicing.money(order.amount_paid),
            balance=invoicing.money(
                Decimal(str(net_total + vat_total)) - Decimal(str(order.amount_paid))
            ),
            notes=order.notes,
        ),
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


@dataclass
class ItemAllocation:
    order_item: OrderItem
    approved: Decimal | int
    reserved: Decimal  # how much stock we could actually hold (≤ approved)


def _reserve_item(item: OrderItem, depot_id: int, user: User | None) -> ItemAllocation:
    """Reserve up to the approved quantity from the depot's FEFO batches."""
    remaining = Decimal(item.quantity_approved)
    batches = (
        InventoryBatch.objects.select_for_update()
        .filter(
            organization_id=depot_id,
            product=item.product,
            status=InventoryBatch.Status.ACTIVE,
            # Never ship expired stock. FEFO orders by expiry, so without this the
            # soonest-expiring batch is picked *first* — meaning expired goods are
            # not merely reachable, they are preferred.
            expiry_date__gte=timezone.localdate(),
        )
        .order_by("expiry_date", "batch_number")  # FEFO
    )
    reserved = Decimal(0)
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
        batch.quantity_reserved = max(Decimal(0), batch.quantity_reserved - res.quantity)
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
    shipped: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    for res in order.reservations.select_related("batch", "order_item").select_for_update():
        batch = res.batch
        # Reserved stock physically leaves the depot: reduce both counters.
        batch.quantity_available -= res.quantity
        batch.quantity_reserved = max(Decimal(0), batch.quantity_reserved - res.quantity)
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
        item.quantity_shipped = shipped.get(item.pk, Decimal(0))
        item.save(update_fields=["quantity_shipped"])
        # A tender is drawn down by what actually ships, not what was ordered —
        # otherwise a cancelled or short line silently consumes committed volume.
        _draw_down_tender(order=order, item=item, quantity=item.quantity_shipped)

    order.status = StockOrder.Status.IN_TRANSIT
    order.save(update_fields=["status", "updated_at"])
    _generate_delivery_note(order, shipment, user)
    return shipment


def _draw_down_tender(*, order: StockOrder, item: OrderItem, quantity: Decimal | int) -> None:
    """Consume committed volume on the tender contract this line was priced under."""
    if quantity <= 0:
        return
    from apps.distribution.marketplace import active_contract

    contract = active_contract(depot=order.depot_id, product=item.product_id, buyer=order.retail_id)
    if contract is None:
        return
    remaining = contract.total_committed_qty - contract.drawn_qty
    contract.drawn_qty += min(Decimal(quantity), max(Decimal(0), Decimal(remaining)))
    contract.save(update_fields=["drawn_qty"])


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
    received_per_item: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    any_discrepancy = False
    for line in grn.lines.select_related("order_item", "product").all():
        data = lines_data.get(line.pk, {})
        line.quantity_received = int(data.get("quantity_received", line.quantity_received))
        line.quantity_damaged = int(data.get("quantity_damaged", 0))
        line.save(update_fields=["quantity_received", "quantity_damaged"])

        good = max(Decimal(0), line.quantity_received - line.quantity_damaged)
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
                # What the depot itself paid. The transfer price above carries the
                # depot's margin, which is not group profit until the goods leave
                # the group — consolidation eliminates the difference.
                origin_unit_cost=_depot_cost(grn.order.depot, line.product, line.batch_number),
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


def _depot_cost(depot: Any, product: Any, batch_number: str) -> Decimal | None:
    """What the sending depot paid for this lot, if it still knows.

    Returns None rather than guessing when the depot's own batch has gone or was
    never costed: consolidation reports unmeasured transfers separately instead of
    assuming they carried no margin.
    """
    from apps.inventory.models import InventoryBatch

    source = (
        InventoryBatch.objects.filter(
            organization=depot, product=product, batch_number=batch_number
        )
        .order_by("id")
        .first()
    )
    if source is None:
        return None
    # A lot the depot itself received from elsewhere in the group keeps the
    # original cost, so margin cannot be laundered by transferring twice.
    return source.origin_unit_cost or source.wholesale_cost
