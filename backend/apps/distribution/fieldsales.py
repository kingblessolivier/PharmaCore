"""Van sales: stock that travels with a rep, and how reps are actually performing.

A van is a moving warehouse. Loading it must take the goods out of the depot, not
merely note that someone intends to carry them; selling from it must take them out
of the van; and whatever comes back at the end of the day must reconcile against
what went out. Previously ``VanStock`` was a quantity nobody could account for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.distribution.models import (
    SalesRepresentative,
    SalesVisitLog,
    StockOrder,
    VanStock,
    VanStockMovement,
)
from apps.inventory.models import InventoryBatch, StockMovement
from apps.inventory.services import receive_intake

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.catalog.models import Product
    from apps.iam.models import User

ZERO = Decimal("0.00")


class VanError(Exception):
    """Raised when a van operation would leave stock unaccounted for."""


@transaction.atomic
def load_van(
    *,
    rep: SalesRepresentative,
    product: Product,
    batch_number: str,
    quantity: int,
    user: User | None = None,
) -> VanStock:
    """Move stock from the depot into a rep's van.

    The units leave depot on-hand at this point. A van holding goods the depot
    still counts as its own is the single most common way van sales lose stock.
    """
    if quantity <= 0:
        raise VanError("Load quantity must be positive.")

    batch = (
        InventoryBatch.objects.select_for_update()
        .filter(
            organization=rep.organization,
            product=product,
            batch_number=batch_number,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        )
        .first()
    )
    if batch is None:
        raise VanError(
            f"No active, unexpired batch '{batch_number}' of {product} at "
            f"{rep.organization.name}."
        )
    free = batch.quantity_available - batch.quantity_reserved
    if free < quantity:
        raise VanError(f"Only {free} unit(s) of batch '{batch_number}' are free to load.")

    batch.quantity_available -= quantity
    batch.save(update_fields=["quantity_available", "updated_at"])
    StockMovement.objects.create(
        organization=rep.organization,
        product=product,
        batch=batch,
        batch_number=batch_number,
        movement_type=StockMovement.Type.TRANSFER_OUT,
        quantity_delta=-quantity,
        reference_type="van_load",
        reference_id=str(rep.pk),
        created_by=user,
    )

    van, _ = VanStock.objects.select_for_update().get_or_create(
        rep=rep, product=product, batch_number=batch_number, defaults={"quantity": 0}
    )
    van.quantity += quantity
    van.save(update_fields=["quantity"])
    VanStockMovement.objects.create(
        rep=rep,
        product=product,
        batch_number=batch_number,
        kind=VanStockMovement.Kind.LOAD,
        quantity=quantity,
        recorded_by=user,
    )
    return van


@transaction.atomic
def sell_from_van(
    *,
    rep: SalesRepresentative,
    product: Product,
    batch_number: str,
    quantity: int,
    visit: SalesVisitLog | None = None,
    reference: str = "",
    user: User | None = None,
) -> VanStock:
    """Record a sale off the van. The goods are already out of the depot."""
    if quantity <= 0:
        raise VanError("Sale quantity must be positive.")
    van = (
        VanStock.objects.select_for_update()
        .filter(rep=rep, product=product, batch_number=batch_number)
        .first()
    )
    if van is None or van.quantity < quantity:
        held = van.quantity if van else 0
        raise VanError(
            f"The van holds {held} unit(s) of '{batch_number}' — cannot sell {quantity}."
        )

    van.quantity -= quantity
    van.save(update_fields=["quantity"])
    VanStockMovement.objects.create(
        rep=rep,
        product=product,
        batch_number=batch_number,
        kind=VanStockMovement.Kind.SALE,
        quantity=-quantity,
        visit=visit,
        reference=reference,
        recorded_by=user,
    )
    return van


@transaction.atomic
def return_to_depot(
    *,
    rep: SalesRepresentative,
    product: Product,
    batch_number: str,
    quantity: int,
    expiry_date: Any = None,
    user: User | None = None,
) -> VanStock:
    """Bring unsold van stock back into the depot at end of round."""
    if quantity <= 0:
        raise VanError("Return quantity must be positive.")
    van = (
        VanStock.objects.select_for_update()
        .filter(rep=rep, product=product, batch_number=batch_number)
        .first()
    )
    if van is None or van.quantity < quantity:
        held = van.quantity if van else 0
        raise VanError(
            f"The van holds {held} unit(s) of '{batch_number}' — cannot return {quantity}."
        )

    if expiry_date is None:
        # Prefer the batch's own expiry; the van record does not carry one.
        existing = InventoryBatch.objects.filter(
            organization=rep.organization, product=product, batch_number=batch_number
        ).first()
        if existing is None:
            raise VanError(
                f"Batch '{batch_number}' is unknown at the depot — an expiry date is required "
                "to take it back into stock."
            )
        expiry_date = existing.expiry_date

    van.quantity -= quantity
    van.save(update_fields=["quantity"])
    receive_intake(
        organization=rep.organization,
        product=product,
        batch_number=batch_number,
        expiry_date=expiry_date,
        quantity=quantity,
        user=user,
        movement_type=StockMovement.Type.TRANSFER_IN,
        reference_type="van_return",
        reference_id=str(rep.pk),
    )
    VanStockMovement.objects.create(
        rep=rep,
        product=product,
        batch_number=batch_number,
        kind=VanStockMovement.Kind.RETURN,
        quantity=-quantity,
        recorded_by=user,
    )
    return van


def van_manifest(*, rep: SalesRepresentative) -> dict[str, Any]:
    """What is on the van right now, and what has moved through it."""
    holdings = list(VanStock.objects.filter(rep=rep, quantity__gt=0).select_related("product"))
    moves = VanStockMovement.objects.filter(rep=rep)
    loaded = moves.filter(kind=VanStockMovement.Kind.LOAD).aggregate(t=Sum("quantity"))["t"] or 0
    sold = moves.filter(kind=VanStockMovement.Kind.SALE).aggregate(t=Sum("quantity"))["t"] or 0
    returned = (
        moves.filter(kind=VanStockMovement.Kind.RETURN).aggregate(t=Sum("quantity"))["t"] or 0
    )
    on_van = sum(h.quantity for h in holdings)
    return {
        "rep": rep.pk,
        "rep_name": rep.user.get_full_name() or rep.user.username,
        "lines": [
            {
                "product": h.product_id,
                "product_name": str(h.product),
                "batch_number": h.batch_number,
                "quantity": h.quantity,
            }
            for h in holdings
        ],
        "units_on_van": on_van,
        "units_loaded": int(loaded),
        "units_sold": int(-sold),
        "units_returned": int(-returned),
        # Loaded − sold − returned should equal what is still aboard. Anything else
        # is stock that left the depot and cannot be pointed at.
        "reconciles": int(loaded) + int(sold) + int(returned) == on_van,
    }


@dataclass
class RepPerformance:
    """A rep's actual sales against the target they carry."""

    rep: SalesRepresentative
    orders: int
    revenue: Decimal
    target: Decimal
    commission: Decimal
    visits: int
    visits_converted: int

    @property
    def attainment_pct(self) -> float:
        return float(self.revenue / self.target * 100) if self.target else 0.0

    @property
    def conversion_pct(self) -> float:
        return (self.visits_converted / self.visits * 100) if self.visits else 0.0


def performance(*, rep: SalesRepresentative, start: Any, end: Any) -> RepPerformance:
    """Compute a rep's attainment and commission from real orders.

    ``monthly_sales_target`` and ``commission_rate_pct`` had driven no calculation
    anywhere; this is what they are for. Revenue counts orders that actually
    shipped — an order that was cancelled earns no commission.
    """
    orders = StockOrder.objects.filter(
        depot=rep.organization,
        ordered_by=rep.user,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).exclude(status=StockOrder.Status.CANCELLED)

    revenue = ZERO
    counted = 0
    for order in orders.prefetch_related("items"):
        revenue += Decimal(str(order.total_amount))
        counted += 1

    visits = SalesVisitLog.objects.filter(
        rep=rep, visited_at__date__gte=start, visited_at__date__lte=end
    )
    return RepPerformance(
        rep=rep,
        orders=counted,
        revenue=revenue.quantize(Decimal("0.01")),
        target=Decimal(rep.monthly_sales_target),
        commission=(revenue * Decimal(rep.commission_rate_pct) / 100).quantize(Decimal("0.01")),
        visits=visits.count(),
        # A visit that produced an order is the only visit that paid for itself.
        visits_converted=visits.exclude(order=None).count(),
    )
