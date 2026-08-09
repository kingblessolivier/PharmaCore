"""The wholesale storefront: what a depot offers, at what price, to whom.

A depot is not obliged to sell everything it holds. It publishes a listing per
product carrying an offered quantity, a buffer it keeps back for itself, a price,
a minimum order and a customer segment. This module is the single authority on
what a retail buyer may actually take, and for how much.

Two numbers are easy to confuse:

``offered_qty``      what the depot has published — a commercial decision.
``physical_free``    what it actually holds unreserved and unexpired — a fact.

Neither alone is safe to sell against. Publishing 10,000 units you do not hold
oversells; holding 10,000 you chose not to publish does not entitle a buyer to
them. Available-to-promise is the smaller of the two, after the buffer is removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import F, Sum
from django.utils import timezone

from apps.distribution.models import DepotProductListing, TenderContract
from apps.inventory.models import InventoryBatch

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.catalog.models import Product
    from apps.iam.models import Organization

ZERO = Decimal("0.00")


def _pk(value: Any) -> int:
    """Accept a model instance or a raw id and return the id.

    Every public function here takes ``Organization | int`` so callers need not
    fetch a row just to pass it. Narrowing in one place keeps that convenience
    without scattering ``getattr(x, "pk", x)`` through the query layer.
    """
    return value if isinstance(value, int) else int(value.pk)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def physical_free(*, depot: Organization | int, product: Product | int) -> int:
    """Unreserved, unexpired, active stock the depot physically holds.

    Expired batches are excluded here and not merely at reservation time, so the
    storefront never advertises stock that could not lawfully be shipped.
    """
    depot_id = _pk(depot)
    product_id = _pk(product)
    agg = (
        InventoryBatch.objects.filter(
            organization_id=depot_id,
            product_id=product_id,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        )
        .annotate(free=F("quantity_available") - F("quantity_reserved"))
        .filter(free__gt=0)
        .aggregate(total=Sum("free"))
    )
    return int(agg["total"] or 0)


def _implicit_offer(*, depot_id: int, product_id: int, free: int) -> Availability:
    """Fall back to the depot's inventory record when it has published no listing.

    Two ways of saying "we sell this" predate each other. ``PharmacyProduct``
    carries a wholesale price and an active flag — an *implicit* offer, with no
    quantity control, no buffer and no segment. ``DepotProductListing`` is the
    *explicit* storefront offer that supersedes it entirely.

    A depot that has published a listing gets the full set of controls. One that
    has not keeps trading exactly as before, limited only by physical stock — which
    is still a tightening, because the implicit offer never checked stock at all.
    """
    from apps.inventory.models import PharmacyProduct

    offer = PharmacyProduct.objects.filter(
        organization_id=depot_id, product_id=product_id, is_active=True
    ).first()
    if offer is None or offer.wholesale_price is None:
        return Availability(
            listing=None,
            physical_free=free,
            offered=0,
            buffer=0,
            available=0,
            price=ZERO,
            min_order_qty=1,
            order_multiple=1,
            is_listed=False,
            reason="not offered by this depot",
        )
    return Availability(
        listing=None,
        physical_free=free,
        offered=free,
        buffer=0,
        available=free,
        price=Decimal(offer.wholesale_price),
        min_order_qty=1,
        order_multiple=1,
        is_listed=True,
        reason="" if free else "out of stock",
    )


@dataclass(frozen=True)
class Availability:
    """What a buyer may take of one product from one depot, and why."""

    listing: DepotProductListing | None
    physical_free: int
    offered: int
    buffer: int
    available: int
    price: Decimal
    min_order_qty: int
    #: Orders must be a whole multiple of this. A case is not opened to fill an
    #: order, so a depot shipping by the case sells 5 or 10, never 7.
    order_multiple: int
    is_listed: bool
    reason: str = ""

    @property
    def is_orderable(self) -> bool:
        return self.is_listed and self.available > 0


def availability(
    *,
    depot: Organization | int,
    product: Product | int,
    buyer: Organization | int | None = None,
) -> Availability:
    """Resolve what ``buyer`` may order of ``product`` from ``depot``.

    An unlisted, unpublished or segment-excluded product is not an error — it
    returns ``is_listed=False`` with a reason, and the caller decides whether to
    refuse the line or capture it as demand. That distinction is what lets a
    retailer order something the depot does not yet stock.
    """
    depot_id = _pk(depot)
    product_id = _pk(product)
    listing = DepotProductListing.objects.filter(depot_id=depot_id, product_id=product_id).first()
    free = physical_free(depot=depot_id, product=product_id)

    if listing is None:
        return _implicit_offer(depot_id=depot_id, product_id=product_id, free=free)

    if not listing.is_published:
        return Availability(
            listing=listing,
            physical_free=free,
            offered=listing.offered_qty,
            buffer=listing.buffer_qty,
            available=0,
            price=listing.price_per_unit,
            min_order_qty=listing.min_order_qty,
            order_multiple=listing.order_multiple,
            is_listed=False,
            reason="withdrawn from sale by the depot",
        )

    if buyer is not None and not segment_matches(listing, buyer):
        return Availability(
            listing=listing,
            physical_free=free,
            offered=listing.offered_qty,
            buffer=listing.buffer_qty,
            available=0,
            price=listing.price_per_unit,
            min_order_qty=listing.min_order_qty,
            order_multiple=listing.order_multiple,
            is_listed=False,
            reason=f"restricted to {listing.customer_segment} customers",
        )

    sellable = max(0, free - listing.buffer_qty)
    available = min(listing.offered_qty, sellable)
    reason = ""
    if available == 0:
        reason = "out of stock" if sellable == 0 else "fully allocated"
    elif available < listing.offered_qty:
        reason = "limited by stock on hand"

    return Availability(
        listing=listing,
        physical_free=free,
        offered=listing.offered_qty,
        buffer=listing.buffer_qty,
        available=available,
        price=price_for(depot=depot_id, product=product_id, buyer=buyer, listing=listing),
        min_order_qty=listing.min_order_qty,
        order_multiple=listing.order_multiple,
        is_listed=True,
        reason=reason,
    )


def segment_matches(listing: DepotProductListing, buyer: Organization | int) -> bool:
    """Is this buyer inside the listing's customer segment?

    ``ALL`` (or blank) means unrestricted. Otherwise the segment names either an
    organization type (``RETAIL``, ``HQ``) or a place the buyer is in — its
    province or district — which is how a depot restricts an offer to the
    territory it can actually deliver to.
    """
    segment = (listing.customer_segment or "ALL").strip().upper()
    if segment in ("", "ALL"):
        return True

    from apps.iam.models import Organization as Org

    buyer_obj = buyer if isinstance(buyer, Org) else Org.objects.filter(pk=buyer).first()
    if buyer_obj is None:
        return False
    return segment in {
        buyer_obj.type.strip().upper(),
        buyer_obj.province.strip().upper(),
        buyer_obj.district.strip().upper(),
    }


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


def active_contract(
    *, depot: Organization | int, product: Product | int, buyer: Organization | int | None
) -> TenderContract | None:
    """The live tender contract governing this pair, if any.

    A contract only governs while it is active, in date, and has volume left to
    draw. Past any of those the buyer reverts to storefront pricing rather than
    silently continuing at the tender rate.
    """
    if buyer is None:
        return None
    return (
        TenderContract.objects.filter(
            depot_id=_pk(depot),
            product_id=_pk(product),
            client_org_id=_pk(buyer),
            is_active=True,
            valid_until__gte=timezone.localdate(),
        )
        .filter(drawn_qty__lt=F("total_committed_qty"))
        .order_by("-created_at")
        .first()
    )


def price_for(
    *,
    depot: Organization | int,
    product: Product | int,
    buyer: Organization | int | None,
    listing: DepotProductListing | None = None,
) -> Decimal:
    """The price this buyer pays — an awarded tender price beats the list price."""
    contract = active_contract(depot=depot, product=product, buyer=buyer)
    if contract is not None:
        return Decimal(contract.contract_price)
    if listing is None:
        listing = DepotProductListing.objects.filter(
            depot_id=_pk(depot), product_id=_pk(product)
        ).first()
    if listing is not None:
        return Decimal(listing.price_per_unit)
    # No storefront listing — fall back to the implicit inventory offer.
    from apps.inventory.models import PharmacyProduct

    offer = PharmacyProduct.objects.filter(
        organization_id=_pk(depot),
        product_id=_pk(product),
        is_active=True,
    ).first()
    return Decimal(offer.wholesale_price) if offer and offer.wholesale_price else ZERO


# ---------------------------------------------------------------------------
# Line validation — the decision that makes demand capture possible
# ---------------------------------------------------------------------------


@dataclass
class LineDecision:
    """How much of a requested line can be sold, and what is left wanting.

    ``fulfillable`` goes on the order. ``backordered`` becomes a demand signal the
    depot can import against. A line is never silently dropped: the two always sum
    to what was asked for.
    """

    product: Product
    requested: int
    fulfillable: int
    backordered: int
    price: Decimal
    availability: Availability
    note: str = ""

    @property
    def is_short(self) -> bool:
        return self.backordered > 0


def _depot_label(avail: Availability) -> str:
    """The depot's name for a refusal message, from what we already loaded."""
    listing = avail.listing
    return listing.depot.name if listing is not None else "The depot"


def decide_line(
    *,
    depot: Organization | int,
    buyer: Organization | int,
    product: Product,
    quantity: int,
    allow_backorder: bool = True,
) -> LineDecision:
    """Split one requested line into what can ship now and what must be sourced."""
    avail = availability(depot=depot, product=product, buyer=buyer)

    if not avail.is_listed:
        # Nothing to sell today. Under backorder this is the demand signal the
        # depot imports against; without it, the line simply cannot be placed.
        return LineDecision(
            product=product,
            requested=quantity,
            fulfillable=0,
            backordered=quantity if allow_backorder else 0,
            price=avail.price,
            availability=avail,
            note=avail.reason,
        )

    sellable = min(quantity, avail.available)
    # A minimum order quantity applies to what actually ships. Shipping fewer than
    # the depot's minimum is not a partial win — it is a line that cannot be filled.
    if sellable < avail.min_order_qty:
        return LineDecision(
            product=product,
            requested=quantity,
            fulfillable=0,
            backordered=quantity if allow_backorder else 0,
            price=avail.price,
            availability=avail,
            note=(
                f"minimum order is {avail.min_order_qty}"
                if quantity < avail.min_order_qty
                else f"only {avail.available} available, below the minimum order of "
                f"{avail.min_order_qty}"
            ),
        )

    # Round down to a whole multiple of what the depot ships in. A case is not
    # opened to fill an order, so asking for 7 of something sold in fives gets 5
    # shipped and 2 recorded as demand — rather than a quantity the depot cannot
    # actually pick, discovered on the loading bay.
    multiple = max(1, avail.order_multiple)
    if multiple > 1:
        shippable = (sellable // multiple) * multiple
        if shippable < avail.min_order_qty:
            return LineDecision(
                product=product,
                requested=quantity,
                fulfillable=0,
                backordered=quantity if allow_backorder else 0,
                price=avail.price,
                availability=avail,
                note=(
                    f"{_depot_label(avail)} ships in multiples of {multiple}; "
                    f"{sellable} rounds below the minimum order of {avail.min_order_qty}"
                ),
            )
        sellable = shippable

    short = quantity - sellable
    return LineDecision(
        product=product,
        requested=quantity,
        fulfillable=sellable,
        backordered=short if allow_backorder else 0,
        price=avail.price,
        availability=avail,
        note=f"{short} beyond available stock" if short else "",
    )


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


@dataclass
class ListingView:
    """A storefront row as a buyer sees it."""

    listing: DepotProductListing
    available: int
    price: Decimal
    physical_free: int = 0
    show_stock_detail: bool = False


def storefront(
    *,
    depot: Organization | int,
    buyer: Organization | int | None = None,
    include_unlisted: bool = False,
) -> list[ListingView]:
    """Every product a buyer can see from this depot, with live availability.

    The depot's own physical holding is deliberately *not* exposed to a buyer —
    only what has been offered. A depot may hold stock it has chosen not to show,
    and the storefront must not leak it.
    """
    qs = DepotProductListing.objects.filter(depot_id=_pk(depot)).select_related("product", "depot")
    if not include_unlisted:
        qs = qs.filter(is_published=True)

    rows: list[ListingView] = []
    for listing in qs:
        avail = availability(depot=listing.depot_id, product=listing.product_id, buyer=buyer)
        if not include_unlisted and not avail.is_listed:
            continue
        rows.append(
            ListingView(
                listing=listing,
                available=avail.available,
                price=avail.price,
                physical_free=avail.physical_free if include_unlisted else 0,
                show_stock_detail=include_unlisted,
            )
        )
    return rows


def publish(
    *,
    depot: Organization | int,
    product: Product | int,
    offered_qty: int,
    price_per_unit: Decimal,
    buffer_qty: int = 0,
    min_order_qty: int = 1,
    customer_segment: str = "ALL",
    is_published: bool = True,
) -> DepotProductListing:
    """Create or update a storefront listing.

    Offering more than is held is permitted — a depot may publish against stock it
    has on order — but it is reported, because availability will silently cap it.
    """
    depot_id = _pk(depot)
    product_id = _pk(product)
    listing, _ = DepotProductListing.objects.update_or_create(
        depot_id=depot_id,
        product_id=product_id,
        defaults={
            "offered_qty": offered_qty,
            "buffer_qty": buffer_qty,
            "price_per_unit": price_per_unit,
            "min_order_qty": max(1, min_order_qty),
            "customer_segment": customer_segment or "ALL",
            "is_published": is_published,
        },
    )
    return listing


def coverage(*, depot: Organization | int) -> dict[str, object]:
    """How much of what the depot holds is actually on sale.

    A depot that holds 200 lines and publishes 12 is not running a marketplace,
    and no one downstream can tell without this.
    """
    depot_id = _pk(depot)
    held = (
        InventoryBatch.objects.filter(
            organization_id=depot_id,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
            quantity_available__gt=0,
        )
        .values("product_id")
        .distinct()
        .count()
    )
    listings = DepotProductListing.objects.filter(depot_id=depot_id)
    published = listings.filter(is_published=True).count()
    withheld = listings.filter(is_published=False).count()

    oversold: list[dict[str, object]] = []
    for listing in listings.filter(is_published=True).select_related("product"):
        free = physical_free(depot=depot_id, product=listing.product_id)
        if listing.offered_qty > max(0, free - listing.buffer_qty):
            oversold.append(
                {
                    "product": listing.product_id,
                    "product_name": str(listing.product),
                    "offered": listing.offered_qty,
                    "sellable": max(0, free - listing.buffer_qty),
                }
            )

    return {
        "products_held": held,
        "listings": listings.count(),
        "published": published,
        "withheld": withheld,
        "unlisted": max(0, held - listings.count()),
        "oversold": oversold,
    }
