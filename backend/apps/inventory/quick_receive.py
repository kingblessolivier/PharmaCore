"""Receiving stock that arrived without a purchase order.

Every existing path into inventory runs through procurement: raise a
requisition, approve it, issue a purchase order, receive against it with a GRN.
That is the correct shape for a depot buying by the pallet, and it is not how a
community pharmacy buys.

A rep's van stops outside, the pharmacist buys four boxes of amoxicillin and
two of ORS, pays cash, and the stock is on the shelf ten minutes later. There
was never an order to receive against. Until now the only way to record that was
to invent a purchase order after the fact, which is paperwork describing
something that did not happen — so in practice it does not get recorded at all,
and the shelf and the system disagree from the first week.

The nearest thing that existed, ``IntakeView``, refuses outright:

    "Only depots receive supplier intake. Retail branches get stock via
    transfers."

That is correct for a branch of a chain, which is supplied by its own depot. It
is wrong for an independent community pharmacy, which has no depot behind it and
buys its own stock — and that is most of them here.

So the two paths are deliberately symmetric rather than merged. ``IntakeView``
is a depot receiving a bulk supplier delivery, with a supplier record, a storage
location and a manufacture date. This is a shop buying four boxes at the door.
Each refuses the other's organisation type, so neither can be used to dodge the
other's controls.

One call, the six things a pharmacist actually knows, and the stock is in.

**What it does not do is skip anything that matters.** Batch and expiry are
required, because traceability to the lot is the whole basis of a recall and
Rwandan Good Pharmacy Practice is built on it. The cost is required because
without it the pharmacy's margin is fiction. What is skipped is the *ceremony* —
the order, the approval, the three-way match — none of which describes anything
real when the goods are already on the counter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement
from apps.inventory.services import receive_intake


class QuickReceiveError(ValueError):
    """The delivery as described could not be received."""


def _plain(value: Decimal) -> str:
    """A quantity as a person writes it.

    `Decimal.normalize()` turns 20 into "2E+1", which is correct and unreadable
    on a screen that says how many boxes just went on the shelf.
    """
    quantised = value.quantize(Decimal("0.001")).normalize()
    return f"{quantised:f}"


@transaction.atomic
def quick_receive(
    *,
    organization: Organization,
    product: Product,
    quantity: Decimal | int,
    batch_number: str,
    expiry_date: date,
    unit_cost: Decimal,
    selling_price: Decimal | None = None,
    supplier_name: str = "",
    user: User | None = None,
) -> dict[str, Any]:
    """Put a delivery on the shelf, and say what changed.

    Returns what happened rather than the batch alone, because the person doing
    this is standing at a counter and needs to see three things: that it went
    in, what the shelf now holds, and what they will make on it.
    """
    # The mirror image of IntakeView's rule, and for the same reason: a depot
    # has a supplier ledger, a receiving bay and a three-way match, and letting
    # it bypass all three through the small-pharmacy door would make this an
    # exploit rather than an adaptation.
    if organization.type == Organization.OrgType.DEPOT:
        raise QuickReceiveError(
            "A depot receives stock against a purchase order, so the delivery can be "
            "matched to what was ordered and what was invoiced. Use supplier intake."
        )

    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise QuickReceiveError("How many did you receive? It has to be more than zero.")
    if not batch_number.strip():
        raise QuickReceiveError(
            "Every delivery needs its batch number. It is what a recall is traced "
            "through, and it is printed on the box."
        )
    if expiry_date <= timezone.localdate():
        raise QuickReceiveError(
            f"That batch expired on {expiry_date:%d %b %Y}. Do not put it on the shelf — "
            "send it back to the supplier."
        )
    unit_cost = Decimal(str(unit_cost))
    if unit_cost <= 0:
        raise QuickReceiveError(
            "What did you pay per unit? Without it the pharmacy cannot tell what it "
            "makes on this medicine."
        )
    if selling_price is not None:
        selling_price = Decimal(str(selling_price))
        if selling_price < unit_cost:
            raise QuickReceiveError(
                f"You would sell at {selling_price:,.0f} what cost you {unit_cost:,.0f}. "
                "Check the prices — as entered, every sale loses money."
            )

    batch = receive_intake(
        organization=organization,
        product=product,
        batch_number=batch_number.strip(),
        expiry_date=expiry_date,
        quantity=quantity,
        wholesale_cost=unit_cost,
        user=user,
        movement_type=StockMovement.Type.INTAKE,
        reference_type="direct_purchase",
        reference_id=supplier_name.strip()[:60],
    )

    # The listing is what the till sells from. A medicine received but never
    # listed is stock the counter cannot find.
    listing, created = PharmacyProduct.objects.get_or_create(
        organization=organization,
        product=product,
        defaults={"is_active": True, "retail_price": selling_price},
    )
    if not created:
        changed = []
        if not listing.is_active:
            listing.is_active = True
            changed.append("is_active")
        if selling_price is not None and listing.retail_price != selling_price:
            listing.retail_price = selling_price
            changed.append("retail_price")
        if changed:
            listing.save(update_fields=changed)

    on_hand = (
        InventoryBatch.objects.filter(
            organization=organization,
            product=product,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        )
        .values_list("quantity_available", flat=True)
        .iterator()
    )
    total = sum((Decimal(str(q or 0)) for q in on_hand), Decimal("0"))

    price = listing.retail_price
    margin_pct = (
        float(((price - unit_cost) / price * 100).quantize(Decimal("0.1")))
        if price and price > 0
        else None
    )

    return {
        "batch": batch.pk,
        "batch_number": batch.batch_number,
        "product": product.pk,
        "product_name": f"{product.generic_name} {product.strength or ''}".strip(),
        "received": _plain(quantity),
        "expiry_date": expiry_date.isoformat(),
        "unit_cost": f"{unit_cost:.2f}",
        "selling_price": None if price is None else f"{Decimal(str(price)):.2f}",
        "margin_pct": margin_pct,
        "on_hand_now": _plain(total),
        "listed": True,
        "newly_listed": created,
        "supplier": supplier_name.strip(),
    }
