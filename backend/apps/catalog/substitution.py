"""What else would do, when the shelf is empty.

``ProductSubstitute`` records generic equivalents and therapeutic alternatives,
and nothing read it. The single most useful thing a catalog knows at an empty
shelf is what to reach for instead, and the till was saying "out of stock" and
stopping.

Two rules that keep the suggestion honest:

* **Only offer what is actually there.** A substitute that is also out of stock
  is worse than no suggestion — it sends the counter on a second search for
  nothing. Every candidate is checked against unreserved, unexpired stock.
* **A generic equivalent is not a therapeutic alternative.** The first is the
  same drug by another name and a pharmacist can usually swap it; the second is
  a different drug for the same purpose and generally needs the prescriber. They
  are returned distinctly rather than as one undifferentiated list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db.models import F, Sum
from django.utils import timezone

from apps.catalog.models import ProductSubstitute

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


@dataclass
class Option:
    """One thing that could be dispensed instead."""

    product_id: int
    product_name: str
    substitute_type: str
    available: int
    notes: str = ""

    @property
    def is_generic(self) -> bool:
        return self.substitute_type == ProductSubstitute.SubstituteType.GENERIC_EQUIVALENT

    def as_dict(self) -> dict[str, Any]:
        return {
            "product": self.product_id,
            "product_name": self.product_name,
            "substitute_type": self.substitute_type,
            "is_generic_equivalent": self.is_generic,
            "available": self.available,
            "notes": self.notes,
        }


def _available(*, organization: Any, product_ids: list[int]) -> dict[int, int]:
    """Unreserved, unexpired stock per product at one pharmacy."""
    from apps.inventory.models import InventoryBatch

    rows = (
        InventoryBatch.objects.filter(
            organization_id=getattr(organization, "pk", organization),
            product_id__in=product_ids,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        )
        .annotate(free=F("quantity_available") - F("quantity_reserved"))
        .filter(free__gt=0)
        .values("product_id")
        .annotate(total=Sum("free"))
    )
    return {r["product_id"]: int(r["total"] or 0) for r in rows}


def options_for(*, product: Any, organization: Any, in_stock_only: bool = True) -> list[Option]:
    """What could be dispensed instead of ``product`` at this pharmacy.

    Generic equivalents come first: they are the same drug under another name,
    so a pharmacist can usually substitute without going back to the prescriber.
    """
    product_id = getattr(product, "pk", product)
    links = ProductSubstitute.objects.filter(product_id=product_id).select_related(
        "substitute_product"
    )
    if not links:
        return []

    candidate_ids = [ln.substitute_product_id for ln in links]
    stock = _available(organization=organization, product_ids=candidate_ids)

    options = [
        Option(
            product_id=ln.substitute_product_id,
            product_name=str(ln.substitute_product),
            substitute_type=ln.substitute_type,
            available=stock.get(ln.substitute_product_id, 0),
            notes=ln.notes,
        )
        for ln in links
    ]
    if in_stock_only:
        # A suggestion that is also out of stock costs the counter a second
        # search and returns nothing.
        options = [o for o in options if o.available > 0]

    options.sort(key=lambda o: (not o.is_generic, -o.available))
    return options


def suggest(*, product: Any, organization: Any) -> dict[str, Any]:
    """Substitutes in wire form, split by what a pharmacist may decide alone."""
    options = options_for(product=product, organization=organization)
    generics = [o for o in options if o.is_generic]
    alternatives = [o for o in options if not o.is_generic]
    return {
        "product": getattr(product, "pk", product),
        "has_options": bool(options),
        # Same drug, another name — usually the pharmacist's call.
        "generic_equivalents": [o.as_dict() for o in generics],
        # Different drug for the same purpose — usually the prescriber's.
        "therapeutic_alternatives": [o.as_dict() for o in alternatives],
    }
