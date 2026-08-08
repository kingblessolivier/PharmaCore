"""What a product actually sells for.

Two answers to that question existed and only one was ever used. The till reads
``PharmacyProduct.retail_price``; ``PriceList`` and ``ProductPrice`` — with
effective dates, list types and quantity breaks — were a parallel table that
governed nothing. Managing a promotional price list changed no sale.

Resolution order, most specific first:

1. an **active, in-date price list** of the right type, taking the best quantity
   break the line qualifies for;
2. otherwise the pharmacy's own ``retail_price``.

The fallback is deliberate and matches the fix made in Distribution for depot
listings: a pharmacy that never adopted price lists keeps trading exactly as
before, and one that adopts them gets the control it was already being shown.

Where several lists apply, the **lowest** price wins. That is the honest reading
of a promotional list running alongside a standard one — a promotion that
sometimes charged more than the shelf price would be a bug the customer notices
at the till.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import PriceList, ProductPrice

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

ZERO = Decimal("0.00")


@dataclass
class ResolvedPrice:
    """A price, and where it came from — so the till can explain itself."""

    product_id: int
    unit_price: Decimal
    source: str  # PRICE_LIST | PHARMACY | NONE
    price_list_id: int | None = None
    price_list_name: str = ""
    min_quantity: int = 1

    @property
    def from_list(self) -> bool:
        return self.source == "PRICE_LIST"


def active_lists(
    *,
    organization: Any = None,
    at: datetime | None = None,
    list_type: str | None = None,
) -> list[PriceList]:
    """Price lists in force right now **for this organization**.

    A list with no dates is open-ended, which is how most standing lists are set
    up; one with dates only applies inside them.

    ``organization`` is not optional in spirit even though it is in signature:
    omitting it returns every tenant's lists, which is what this function used to
    do unconditionally and is why one pharmacy's promotion repriced its
    competitors. Callers that price a real sale always pass it. A list with no
    organization is group-wide and applies everywhere, which is the HQ case.
    """
    at = at or timezone.now()
    qs = PriceList.objects.filter(is_active=True)
    if organization is not None:
        org_id = getattr(organization, "pk", organization)
        qs = qs.filter(Q(organization_id=org_id) | Q(organization__isnull=True))
    if list_type:
        qs = qs.filter(list_type=list_type)
    return [
        pl
        for pl in qs
        if (pl.effective_from is None or pl.effective_from <= at)
        and (pl.effective_to is None or pl.effective_to >= at)
    ]


def resolve(
    *,
    product: Any,
    organization: Any,
    quantity: int = 1,
    list_type: str = PriceList.ListType.RETAIL,
    at: datetime | None = None,
) -> ResolvedPrice:
    """The price this line should be sold at, and why."""
    product_id = getattr(product, "pk", product)
    lists = active_lists(organization=organization, at=at, list_type=list_type)

    best: ProductPrice | None = None
    if lists:
        candidates = (
            ProductPrice.objects.filter(
                price_list__in=lists, product_id=product_id, min_quantity__lte=quantity
            )
            .select_related("price_list")
            .order_by("unit_price")
        )
        # Lowest price the quantity qualifies for. A promotion that charged more
        # than the standard list would be a bug the customer spots at the till.
        best = candidates.first()

    if best is not None:
        return ResolvedPrice(
            product_id=int(product_id),
            unit_price=Decimal(best.unit_price),
            source="PRICE_LIST",
            price_list_id=best.price_list_id,
            price_list_name=best.price_list.name,
            min_quantity=best.min_quantity,
        )

    from apps.inventory.models import PharmacyProduct

    listing = PharmacyProduct.objects.filter(
        organization_id=getattr(organization, "pk", organization),
        product_id=product_id,
        is_active=True,
    ).first()
    if listing is not None and listing.retail_price is not None:
        return ResolvedPrice(
            product_id=int(product_id),
            unit_price=Decimal(listing.retail_price),
            source="PHARMACY",
        )

    return ResolvedPrice(product_id=int(product_id), unit_price=ZERO, source="NONE")


def price_basket(
    *,
    organization: Any,
    lines: list[dict[str, Any]],
    list_type: str = PriceList.ListType.RETAIL,
    at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Resolve every line, reporting which are on a list and which fell back."""
    out: list[dict[str, Any]] = []
    for raw in lines:
        product = raw["product"]
        quantity = int(raw.get("quantity", 1))
        resolved = resolve(
            product=product,
            organization=organization,
            quantity=quantity,
            list_type=list_type,
            at=at,
        )
        out.append(
            {
                "product": resolved.product_id,
                "quantity": quantity,
                "unit_price": str(resolved.unit_price),
                "line_total": str((resolved.unit_price * quantity).quantize(Decimal("0.01"))),
                "source": resolved.source,
                "price_list": resolved.price_list_id,
                "price_list_name": resolved.price_list_name,
                "min_quantity": resolved.min_quantity,
            }
        )
    return out


def coverage(*, organization: Any) -> dict[str, Any]:
    """How much of what this pharmacy sells is actually priced by a list.

    A pharmacy running two price lists over four products is not running price
    lists, and nothing downstream can tell without this.
    """
    from apps.inventory.models import PharmacyProduct

    org_id = getattr(organization, "pk", organization)
    stocked = set(
        PharmacyProduct.objects.filter(organization_id=org_id, is_active=True).values_list(
            "product_id", flat=True
        )
    )
    lists = active_lists(organization=org_id)
    priced = set(
        ProductPrice.objects.filter(price_list__in=lists).values_list("product_id", flat=True)
    )
    return {
        "active_lists": len(lists),
        "products_stocked": len(stocked),
        "priced_by_list": len(stocked & priced),
        "falling_back": len(stocked - priced),
        "lists": [
            {
                "id": pl.pk,
                "name": pl.name,
                "type": pl.list_type,
                "products": ProductPrice.objects.filter(price_list=pl).count(),
                "effective_from": pl.effective_from,
                "effective_to": pl.effective_to,
            }
            for pl in lists
        ],
    }
