"""What a medicine needs from the people who move it, and how big a load is.

The catalogue could state one handling requirement — temperature — which
quietly assumes the freezer is the only thing that can ruin a medicine. It is
not. A cytotoxic needs segregation and a spill kit and is not controlled at
all; ceftriaxone browns in daylight; effervescent tablets collapse in Kigali
humidity once the tube is open. None of that could be recorded, so a picker
had no way to know and a packer no reason to do anything differently.

The second half of this module answers a question procurement could not ask:
how big is this order. Freight is charged on whichever of weight or volume is
larger, and a cold box holds a fixed number of litres — so "will this fit in
one cold box, and what will the airline charge" needed both numbers and had
neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.catalog.models import Product, ProductUnit

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

#: Volumetric divisor for air freight: 1 m³ ≈ 167 kg chargeable. Expressed per
#: millilitre so it composes with the units stored on ProductUnit.
AIR_FREIGHT_G_PER_ML = Decimal("0.167")


@dataclass(frozen=True)
class HandlingRequirement:
    """One thing a person must do differently because of what this is."""

    code: str
    label: str
    detail: str
    #: Whether ignoring this ruins the medicine or hurts the handler, as
    #: opposed to merely being untidy. Drives whether a screen shouts.
    critical: bool = False


def requirements_for(product: Product) -> list[HandlingRequirement]:
    """Everything that changes how this product is stored, picked or packed.

    Returned as a list rather than a set of booleans because the caller is
    almost always about to show a person a list of instructions, and deciding
    the wording at each call site is how two screens end up disagreeing about
    what a cytotoxic needs.
    """
    out: list[HandlingRequirement] = []

    if product.storage_condition == Product.Storage.COLD_CHAIN:
        span = _temperature_span(product, default="2 °C to 8 °C")
        out.append(
            HandlingRequirement(
                "COLD_CHAIN",
                "Cold chain",
                f"Keep at {span}. Move in a cold box; log the temperature on hand-over.",
                critical=True,
            )
        )
    elif product.storage_condition == Product.Storage.FROZEN:
        span = _temperature_span(product, default="−25 °C to −15 °C")
        out.append(
            HandlingRequirement(
                "FROZEN",
                "Frozen",
                f"Keep at {span}. Do not allow it to thaw in transit.",
                critical=True,
            )
        )

    if product.hazard_class and product.hazard_class != Product.Hazard.NONE:
        out.append(_hazard_requirement(product.hazard_class))

    if product.light_sensitive:
        out.append(
            HandlingRequirement(
                "LIGHT",
                "Keep out of daylight",
                "Leave it in its carton. Do not display it on an open shelf or a window bay.",
                critical=True,
            )
        )

    if product.humidity_sensitive:
        out.append(
            HandlingRequirement(
                "HUMIDITY",
                "Keep dry",
                "Keep the desiccant in the tube and reseal it. Do not de-blister ahead of sale.",
            )
        )

    if product.is_controlled_substance:
        # Not a handling hazard — a diversion one. It belongs in the same list
        # because it changes the same things: who may pick it and where it is
        # kept between the shelf and the patient.
        schedule = product.controlled_schedule or "a controlled schedule"
        out.append(
            HandlingRequirement(
                "CONTROLLED",
                "Controlled drug",
                f"Registered under {schedule}. Keep in the CD cabinet; two signatures to move.",
                critical=True,
            )
        )

    return out


def _hazard_requirement(hazard: str) -> HandlingRequirement:
    details: dict[str, str] = {
        Product.Hazard.CYTOTOXIC: (
            "Segregate from other stock. Gloves and gown to pick; keep a spill kit "
            "on the aisle. Waste goes to the cytotoxic stream, never general."
        ),
        Product.Hazard.FLAMMABLE: (
            "Away from heat and direct sun. Observe the quantity limit for the room."
        ),
        Product.Hazard.CORROSIVE: ("Eye protection to handle. Keep contained and upright."),
        Product.Hazard.BIOHAZARD: (
            "Sharps and contaminated waste route only. Do not place in general waste."
        ),
    }
    detail = details.get(hazard, "Handle according to its safety data sheet.")
    labels: dict[str, str] = dict(Product.Hazard.choices)
    label = labels.get(hazard, hazard)
    # Labels read "Cytotoxic — segregate, gloves, spill kit"; the chip wants the
    # name and the detail line carries the rest.
    return HandlingRequirement(str(hazard), label.split(" — ")[0], detail, critical=True)


def _temperature_span(product: Product, *, default: str) -> str:
    if product.min_temp_c is None or product.max_temp_c is None:
        return default
    return f"{product.min_temp_c:g} °C to {product.max_temp_c:g} °C"


# ---------------------------------------------------------------------------
# Dose against stock
# ---------------------------------------------------------------------------


def base_units_for_dose(
    product: Product,
    *,
    dose_amount: Decimal,
    doses_per_day: Decimal,
    days: int,
) -> Decimal | None:
    """How much stock a course of treatment consumes.

    A prescription says "5 mL twice daily for 7 days"; a shelf holds bottles.
    Returns the quantity in the product's *base stock unit*, or ``None`` when
    the product has not been told how the two relate — in which case the
    caller must not guess, because guessing dispenses the wrong amount.
    """
    per_base = product.doses_per_base_unit
    if per_base is None or per_base <= 0:
        return None
    total_dose = Decimal(dose_amount) * Decimal(doses_per_day) * Decimal(days)
    return total_dose / Decimal(per_base)


# ---------------------------------------------------------------------------
# How big is this load
# ---------------------------------------------------------------------------


@dataclass
class Shipment:
    """The physical size of a set of lines, and what is missing from the answer."""

    gross_weight_g: Decimal = Decimal("0")
    volume_ml: Decimal = Decimal("0")
    #: Lines whose unit has no weight or volume recorded. The total is a floor,
    #: not a fact, until this is empty — and a freight quote built on a silent
    #: undercount is worse than no quote.
    unmeasured: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.unmeasured

    @property
    def gross_weight_kg(self) -> Decimal:
        return (self.gross_weight_g / 1000).quantize(Decimal("0.001"))

    @property
    def volume_litres(self) -> Decimal:
        return (self.volume_ml / 1000).quantize(Decimal("0.001"))

    @property
    def chargeable_weight_kg(self) -> Decimal:
        """What an air freight invoice is actually calculated on.

        Carriers bill the greater of actual and volumetric weight, so a pallet
        of empty-ish cartons costs what its size implies rather than what it
        weighs. Quoting on actual weight alone under-reads every bulky order.
        """
        volumetric = self.volume_ml * AIR_FREIGHT_G_PER_ML
        return (max(self.gross_weight_g, volumetric) / 1000).quantize(Decimal("0.001"))


def measure(lines: Iterable[tuple[ProductUnit | None, Decimal | int]]) -> Shipment:
    """Total the weight and volume of ``(unit, quantity)`` pairs.

    Anything without a measurement is named rather than treated as weightless.
    A zero that means "we do not know" and a zero that means "nothing" are the
    same number, and only one of them should reassure a freight forwarder.
    """
    shipment = Shipment()
    for unit, quantity in lines:
        qty = Decimal(str(quantity))
        if unit is None or (unit.gross_weight_g is None and unit.volume_ml is None):
            label = f"{unit.product} ({unit.code})" if unit else "an unidentified line"
            shipment.unmeasured.append(label)
            continue
        if unit.gross_weight_g is not None:
            shipment.gross_weight_g += unit.gross_weight_g * qty
        if unit.volume_ml is not None:
            shipment.volume_ml += unit.volume_ml * qty
        if unit.gross_weight_g is None or unit.volume_ml is None:
            shipment.unmeasured.append(f"{unit.product} ({unit.code})")
    return shipment


def cold_boxes_needed(shipment: Shipment, *, box_capacity_litres: Decimal = Decimal("20")) -> int:
    """How many cold boxes a load needs, rounded up.

    Defaults to a 20 L box, the common vaccine carrier. Returns 0 for an empty
    load rather than 1, so a caller can tell "nothing to move" from "one box".
    """
    if shipment.volume_ml <= 0:
        return 0
    litres = shipment.volume_ml / 1000
    boxes = litres / box_capacity_litres
    return int(boxes) + (1 if boxes % 1 else 0)
