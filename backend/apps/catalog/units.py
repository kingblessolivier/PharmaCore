"""Converting a quantity between the levels a medicine is counted in.

Every unit conversion in the system goes through here. That is the point: the
same goods change unit four times between the factory and the patient, and if
each subsystem multiplies inline then each subsystem gets to round differently
and the disagreement only shows up as missing stock months later.

Two rules the rest of the code should not re-implement:

* **Convert through the base, never level to level.** Every `ProductUnit` states
  its size in base units, so any conversion is one multiply and one divide.
  Walking the chain would compound rounding at each hop.
* **A fraction is a clinical decision, not an arithmetic one.** Splitting is
  approved per product (`Product.divisibility`) and defaults to refusing, because
  a score line is not authority to split and roughly one in ten tablets that get
  split should not have been — an enteric or modified-release coating destroyed
  by halving turns a 24-hour dose into an immediate one. See
  docs/development/medicine-chain-import-to-patient.md §7.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.catalog.models import Product, ProductUnit

#: Quantities are carried to three places. That is enough for halves, quarters
#: and thirds of a tablet to round-trip, and few enough that a stock figure
#: never acquires a tail nobody can explain.
PLACES = Decimal("0.001")


class UnitError(ValueError):
    """A quantity that cannot be honoured as asked.

    Carries a message written for the person at the counter, because that is
    where most of these surface.
    """


@dataclass(frozen=True)
class Quantity:
    """An amount *and* what it is an amount of.

    A bare number is the defect this whole module exists to fix: a depot
    shipping "10" and a pharmacy receiving "10" agree on the number and not on
    the fact.
    """

    amount: Decimal
    unit: ProductUnit

    @property
    def base(self) -> Decimal:
        """The same amount expressed in the product's base unit."""
        return quantize(self.amount * self.unit.factor_to_base)

    def __str__(self) -> str:
        label = self.unit.name or self.unit.get_code_display()
        return f"{normalise(self.amount)} × {label}"


def quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PLACES, rounding=ROUND_HALF_UP)


def normalise(value: Decimal) -> str:
    """Render without a trailing tail: 2.000 reads as 2, 0.500 as 0.5."""
    trimmed = quantize(value).normalize()
    return f"{trimmed:f}"


def to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise UnitError(f"{value!r} is not a quantity.") from exc


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def to_base(*, amount: object, unit: ProductUnit) -> Decimal:
    """How many base units `amount` of `unit` comes to."""
    return quantize(to_decimal(amount) * unit.factor_to_base)


def from_base(*, base_amount: object, unit: ProductUnit) -> Decimal:
    """How many of `unit` a base-unit amount comes to.

    Not rounded to whole units: 15 tablets is 1.5 strips of 10, and saying "1"
    would lose five tablets. Callers that need whole packs ask for whole packs.
    """
    factor = Decimal(unit.factor_to_base)
    if factor <= 0:  # guarded in the database too; belt and braces
        raise UnitError("A unit cannot contain zero base units.")
    return quantize(to_decimal(base_amount) / factor)


def convert(*, amount: object, source: ProductUnit, target: ProductUnit) -> Decimal:
    """Restate `amount` of `source` in `target`, via the base unit."""
    if source.product_id != target.product_id:
        raise UnitError("Those units belong to different products.")
    return from_base(base_amount=to_base(amount=amount, unit=source), unit=target)


# ---------------------------------------------------------------------------
# What may legitimately be asked for
# ---------------------------------------------------------------------------


def smallest_step(product: Product) -> Decimal:
    """The smallest amount of one base unit this product may be dispensed in."""
    divisibility = max(1, int(product.divisibility or 1))
    return quantize(Decimal(1) / Decimal(divisibility))


def validate(*, amount: object, unit: ProductUnit, product: Product | None = None) -> Decimal:
    """Check a requested quantity, returning it quantized, or explain the refusal.

    The refusal messages matter as much as the check. A counter that is told
    only "invalid quantity" will try again with a different number; one that is
    told the tablet is enteric-coated stops and reaches for a different pack.
    """
    product = product or unit.product
    value = quantize(to_decimal(amount))

    if value <= 0:
        raise UnitError("A quantity has to be more than nothing.")

    whole = value == value.to_integral_value()
    if whole:
        return value

    # A fraction of a pack is never meaningful: half a box of 100 is 50 tablets,
    # and the person meant one of those two things.
    if not unit.is_base:
        label = unit.name or unit.get_code_display()
        raise UnitError(
            f"{label} can only be sold whole. To sell part of one, choose the "
            f"{unit.product.base_unit.get_code_display().lower()} instead."
            if unit.product.base_unit
            else f"{label} can only be sold whole."
        )

    divisibility = max(1, int(product.divisibility or 1))
    if divisibility == 1:
        raise UnitError(
            product.split_note
            or f"{product.generic_name} may not be split — it is dispensed whole only."
        )

    step = smallest_step(product)
    if (value / step) != (value / step).to_integral_value():
        allowed = "halves" if divisibility == 2 else f"1/{divisibility}"
        raise UnitError(f"{product.generic_name} may only be split into {allowed}.")

    return value
