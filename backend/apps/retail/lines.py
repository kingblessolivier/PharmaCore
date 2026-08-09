"""Building a sale line that knows which unit it was sold in.

Two paths create sale lines — the counter's offline-replay endpoint and the
`SaleSerializer` — and before this each set `quantity` its own way. With units
in play that is exactly the kind of duplication that goes wrong quietly: one
path converts a pack to tablets and the other does not, and the shelf disagrees
with the receipt.

So both now come through `build_line`, which is the only place that decides what
unit a line is in, whether the amount is allowed, and what it costs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.catalog import units
from apps.catalog.models import Product, ProductUnit

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.retail.models import Sale, SaleItem


def resolve_unit(product: Product, code: str | int | None) -> ProductUnit | None:
    """The unit a line is counted in.

    `code` may be a `ProductUnit` id or a unit code ("PACK"). Absent, the
    product's sale default is used, falling back to its base — which is what
    every line meant before units existed, so an old client that sends no unit
    keeps behaving exactly as it did.
    """
    available = list(product.units.all())
    if not available:
        return None

    if code not in (None, ""):
        as_text = str(code)
        for unit in available:
            if as_text == str(unit.pk) or as_text.upper() == unit.code:
                return unit
        raise units.UnitError(f"{product.generic_name} is not sold in '{code}'.")

    return next(
        (u for u in available if u.is_sale_default),
        next((u for u in available if u.is_base), None),
    )


def price_for(*, unit: ProductUnit | None, base_price: Decimal) -> Decimal:
    """What one of `unit` costs.

    A unit may carry its own price, because a pack is normally cheaper per
    tablet than the loose tablets that come out of it — breaking a pack costs
    the pharmacy the ability to sell or return it sealed. Where no such price is
    recorded the base price simply scales, which is what a pharmacy that has not
    set pack pricing actually wants.
    """
    if unit is None:
        return Decimal(base_price)
    if unit.price is not None:
        return Decimal(unit.price)
    return units.quantize(Decimal(base_price) * unit.factor_to_base).quantize(Decimal("0.01"))


def build_line(
    *,
    sale: Sale,
    product: Product,
    quantity: Any,
    base_price: Decimal,
    tax_rate: Decimal,
    unit_code: str | int | None = None,
) -> SaleItem:
    """Create one validated, dimensioned sale line.

    Raises `units.UnitError` with a message written for the counter when the
    amount asked for is not one this product may be dispensed in.
    """
    from apps.retail.models import SaleItem

    unit = resolve_unit(product, unit_code)
    if unit is None:
        # A product with no unit chain yet: treat the number as base units,
        # which is what it has always been.
        amount = units.quantize(units.to_decimal(quantity))
        if amount <= 0:
            raise units.UnitError("A quantity has to be more than nothing.")
        return SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=amount,
            quantity_base=amount,
            unit_price=Decimal(base_price),
            tax_rate=tax_rate,
        )

    amount = units.validate(amount=quantity, unit=unit, product=product)
    return SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=amount,
        unit=unit,
        quantity_base=units.to_base(amount=amount, unit=unit),
        unit_price=price_for(unit=unit, base_price=base_price),
        tax_rate=tax_rate,
    )
