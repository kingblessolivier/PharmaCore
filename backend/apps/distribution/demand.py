"""Demand-driven sourcing: turning what retailers asked for into what to import.

The marketplace refuses nothing outright. A line the depot cannot fill becomes a
``BackorderLine`` — a durable statement that a named pharmacy wanted a named
product in a named quantity on a named day. Aggregated, those lines are the only
honest answer to "what should we import next", and they are what this module
converts into a purchase requisition.

The import machinery already exists in ``apps.procurement`` (requisition → RFQ →
quote → PO → consignment → receipt). Nothing here duplicates it; this is the
bridge that was missing between the sell side and the buy side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from apps.distribution.models import BackorderLine, StockOrder
from apps.procurement.models import PurchaseRequisition, RequisitionLine

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.catalog.models import Product
    from apps.iam.models import Organization, User


def _pk(value: Any) -> int:
    """Accept a model instance or a raw id and return the id."""
    return value if isinstance(value, int) else int(value.pk)


class DemandError(Exception):
    """Raised when demand cannot be sourced as asked."""


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def capture(
    *,
    depot: Organization | int,
    retail: Organization | int,
    product: Product | int,
    quantity: int,
    origin: str = BackorderLine.Origin.SHORT,
    order: StockOrder | None = None,
    note: str = "",
    user: User | None = None,
) -> BackorderLine | None:
    """Record unmet demand. Returns ``None`` for a zero quantity."""
    if quantity <= 0:
        return None
    return BackorderLine.objects.create(
        depot_id=_pk(depot),
        retail_id=_pk(retail),
        product_id=_pk(product),
        order=order,
        quantity=quantity,
        origin=origin,
        note=note[:255],
        requested_by=user,
    )


def origin_for(availability: Any) -> str:
    """Classify why a line could not be filled, from the storefront's verdict."""
    if availability.listing is None:
        return BackorderLine.Origin.UNLISTED
    if not availability.listing.is_published:
        return BackorderLine.Origin.WITHDRAWN
    if not availability.is_listed:
        # Listed and published but still not sellable to this buyer — the only
        # remaining gate is the customer segment.
        return BackorderLine.Origin.SEGMENT
    return BackorderLine.Origin.SHORT


# ---------------------------------------------------------------------------
# The demand board
# ---------------------------------------------------------------------------


@dataclass
class DemandRow:
    """One product's aggregated open demand at a depot."""

    product_id: int
    product_name: str
    quantity: int
    buyers: int
    lines: int
    oldest: date | None
    sourcing: int = 0

    @property
    def age_days(self) -> int:
        return (timezone.now().date() - self.oldest).days if self.oldest else 0


def demand_board(*, depot: Organization | int, include_sourcing: bool = True) -> list[DemandRow]:
    """Aggregate open demand by product, worst (largest, oldest) first.

    Quantity alone is a poor ranking: one desperate pharmacy asking for 500 is a
    different problem from twenty asking for 25 each. Buyer count is carried so
    the depot can tell those apart.
    """
    statuses = [BackorderLine.Status.OPEN]
    if include_sourcing:
        statuses.append(BackorderLine.Status.SOURCING)

    rows = (
        BackorderLine.objects.filter(depot_id=_pk(depot), status__in=statuses)
        .values("product_id", "product__generic_name", "product__brand_name")
        .annotate(
            quantity=Sum("quantity") - Sum("quantity_fulfilled"),
            buyers=Count("retail_id", distinct=True),
            lines=Count("id"),
            oldest=Min("created_at"),
            sourcing=Count("id", filter=Q(status=BackorderLine.Status.SOURCING)),
        )
        .order_by("-quantity")
    )

    board: list[DemandRow] = []
    for row in rows:
        if (row["quantity"] or 0) <= 0:
            continue
        name = row["product__brand_name"] or row["product__generic_name"] or "—"
        oldest = row["oldest"]
        board.append(
            DemandRow(
                product_id=row["product_id"],
                product_name=name,
                quantity=int(row["quantity"]),
                buyers=int(row["buyers"]),
                lines=int(row["lines"]),
                oldest=oldest.date() if oldest else None,
                sourcing=int(row["sourcing"]),
            )
        )
    return board


def demand_for_product(*, depot: Organization | int, product: Product | int) -> list[BackorderLine]:
    """Who is waiting for this product, oldest request first."""
    return list(
        BackorderLine.objects.filter(
            depot_id=_pk(depot),
            product_id=_pk(product),
            status__in=[BackorderLine.Status.OPEN, BackorderLine.Status.SOURCING],
        )
        .select_related("retail", "product", "order")
        .order_by("created_at")
    )


# ---------------------------------------------------------------------------
# The bridge into procurement
# ---------------------------------------------------------------------------


@transaction.atomic
def raise_requisition_from_demand(
    *,
    depot: Organization | int,
    product_ids: list[int] | None = None,
    user: User | None = None,
    needed_by: date | None = None,
    justification: str = "",
) -> PurchaseRequisition:
    """Convert open retail demand into a purchase requisition at the depot.

    This is the point where the sell side hands over to the buy side: from here the
    existing procurement flow (approve → RFQ → quote → PO → import) takes it. The
    backorders move to ``SOURCING`` and carry a pointer to the requisition, so the
    same demand is never sourced twice.
    """
    depot_id = _pk(depot)
    qs = BackorderLine.objects.select_for_update().filter(
        depot_id=depot_id, status=BackorderLine.Status.OPEN
    )
    if product_ids:
        qs = qs.filter(product_id__in=product_ids)

    lines = list(qs.select_related("product"))
    if not lines:
        raise DemandError("There is no open demand to source.")

    wanted: dict[int, int] = {}
    for line in lines:
        outstanding = line.quantity_outstanding
        if outstanding > 0:
            wanted[line.product_id] = wanted.get(line.product_id, 0) + outstanding
    if not wanted:
        raise DemandError("Every matching demand line is already fulfilled.")

    # Stamp the number through procurement's own gapless sequence.
    # ``requisition_number`` is unique with a blank default, so leaving it unset
    # makes the *next* requisition collide on "".
    from apps.iam.models import Organization
    from apps.procurement.models import NumberSequence
    from apps.procurement.services import next_document_number

    requisition = PurchaseRequisition.objects.create(
        organization_id=depot_id,
        requisition_number=next_document_number(
            Organization.objects.get(pk=depot_id), NumberSequence.Kind.REQUISITION
        ),
        status=PurchaseRequisition.Status.DRAFT,
        priority=PurchaseRequisition.Priority.HIGH,
        needed_by=needed_by,
        justification=(
            justification
            or f"Raised from {len(lines)} open retail backorder(s) across "
            f"{len({ln.retail_id for ln in lines})} customer(s)."
        ),
        requested_by=user,
    )

    for product_id, quantity in wanted.items():
        RequisitionLine.objects.create(
            requisition=requisition,
            product_id=product_id,
            quantity=quantity,
            estimated_unit_cost=_last_known_cost(depot_id, product_id),
            notes="Retail demand",
        )

    BackorderLine.objects.filter(pk__in=[ln.pk for ln in lines]).update(
        status=BackorderLine.Status.SOURCING, requisition=requisition
    )
    return requisition


def _last_known_cost(depot_id: int, product_id: int) -> Decimal:
    """Best available estimate of what this product costs to buy.

    An estimate is all a requisition needs — the real price arrives with the
    supplier quote. Falls back to zero rather than guessing wildly.
    """
    from apps.inventory.models import InventoryBatch

    batch = (
        InventoryBatch.objects.filter(organization_id=depot_id, product_id=product_id)
        .exclude(wholesale_cost=None)
        .order_by("-created_at")
        .first()
    )
    if batch is not None and batch.wholesale_cost is not None:
        return Decimal(batch.wholesale_cost)
    return Decimal("0.00")


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------


@transaction.atomic
def settle_backorders_for(
    *, depot: Organization | int, product: Product | int, quantity: int
) -> list[BackorderLine]:
    """Allocate newly-arrived stock to whoever has been waiting longest.

    First come, first served is the only allocation rule that is defensible without
    a commercial policy behind it. Partial fulfilment is honoured — a line that got
    some of what it asked for stays open for the rest.
    """
    remaining = quantity
    settled: list[BackorderLine] = []
    lines = (
        BackorderLine.objects.select_for_update()
        .filter(
            depot_id=_pk(depot),
            product_id=_pk(product),
            status__in=[BackorderLine.Status.OPEN, BackorderLine.Status.SOURCING],
        )
        .order_by("created_at")
    )
    for line in lines:
        if remaining <= 0:
            break
        take = min(remaining, line.quantity_outstanding)
        if take <= 0:
            continue
        line.quantity_fulfilled += take
        if line.quantity_outstanding == 0:
            line.status = BackorderLine.Status.FULFILLED
        line.save(update_fields=["quantity_fulfilled", "status", "updated_at"])
        remaining -= take
        settled.append(line)
    return settled


@transaction.atomic
def cancel_backorder(*, line: BackorderLine, reason: str = "") -> BackorderLine:
    """Withdraw a demand line — the buyer no longer wants it, or it cannot be sourced."""
    if line.status == BackorderLine.Status.FULFILLED:
        raise DemandError("A fulfilled backorder cannot be cancelled.")
    line.status = BackorderLine.Status.CANCELLED
    if reason:
        line.note = reason[:255]
    line.save(update_fields=["status", "note", "updated_at"])
    return line


def summary(*, depot: Organization | int) -> dict[str, Any]:
    """Headline demand figures for the distribution overview.

    Open and being-sourced demand are reported separately and never summed into a
    single headline. Conflating them shows a manager one number and then raises a
    requisition for a much smaller one — because sourcing only ever picks up what
    is still open. ``units_open`` is the number that matches the button.
    """
    depot_id = _pk(depot)
    board = demand_board(depot=depot_id)
    open_board = demand_board(depot=depot_id, include_sourcing=False)
    open_lines = BackorderLine.objects.filter(
        depot_id=depot_id, status=BackorderLine.Status.OPEN
    ).count()
    sourcing = BackorderLine.objects.filter(
        depot_id=depot_id, status=BackorderLine.Status.SOURCING
    ).count()
    return {
        # Actionable now — what "source this demand" would actually requisition.
        "products_open": len(open_board),
        "units_open": sum(r.quantity for r in open_board),
        # Everything still outstanding, including what is already on order.
        "products_wanted": len(board),
        "units_wanted": sum(r.quantity for r in board),
        "units_sourcing": sum(r.quantity for r in board) - sum(r.quantity for r in open_board),
        "buyers_waiting": len(
            set(
                BackorderLine.objects.filter(
                    depot_id=depot_id,
                    status__in=[BackorderLine.Status.OPEN, BackorderLine.Status.SOURCING],
                ).values_list("retail_id", flat=True)
            )
        ),
        "open_lines": open_lines,
        "sourcing_lines": sourcing,
        "oldest_days": max((r.age_days for r in open_board), default=0),
        "top": [
            {
                "product": r.product_id,
                "product_name": r.product_name,
                "quantity": r.quantity,
                "buyers": r.buyers,
                "age_days": r.age_days,
            }
            for r in board[:8]
        ],
    }
