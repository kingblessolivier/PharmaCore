"""A quantity that knows what it is a quantity of.

Before this, every quantity in the system was a bare integer: a depot shipping
"10" and a pharmacy receiving "10" agreed on the number and not on the fact, and
nothing could detect the disagreement because both sides were internally
consistent. These pin the conversion and the rules about splitting a tablet.

The splitting rules are clinical, not arithmetic — see
docs/development/medicine-chain-import-to-patient.md §7.2.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.catalog import units
from apps.catalog.models import Product, ProductUnit
from apps.catalog.units import UnitError

pytestmark = pytest.mark.django_db


def product(name="Paracetamol", form="TABLET", divisibility=1, note=""):
    return Product.objects.create(
        generic_name=name,
        strength="500mg",
        dosage_form=form,
        divisibility=divisibility,
        split_note=note,
    )


def unit(prod, code, factor, *, level=0, base=False, name=""):
    return ProductUnit.objects.create(
        product=prod,
        code=code,
        name=name,
        factor_to_base=Decimal(str(factor)),
        level=level,
        is_base=base,
    )


@pytest.fixture
def paracetamol():
    """A real chain: a box holds 10 strips of 10 tablets."""
    p = product()
    tablet = unit(p, "TABLET", 1, level=0, base=True)
    strip = unit(p, "STRIP", 10, level=1, name="Strip of 10")
    pack = unit(p, "PACK", 100, level=2, name="Box of 100")
    case = unit(p, "CASE", 2400, level=3, name="Case of 24")
    return p, tablet, strip, pack, case


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def test_a_quantity_carries_the_unit_it_was_counted_in(paracetamol):
    """The whole point: 10 is not a number, it is 10 of something."""
    _, _, _, pack, _ = paracetamol
    q = units.Quantity(amount=Decimal("10"), unit=pack)
    assert q.base == Decimal("1000.000")
    assert str(q) == "10 × Box of 100"


def test_the_depot_and_the_pharmacy_now_agree(paracetamol):
    """A case shipped and a case received are the same 2400 tablets."""
    _, tablet, _, _, case = paracetamol
    shipped = units.to_base(amount=1, unit=case)
    assert shipped == Decimal("2400.000")
    assert units.from_base(base_amount=shipped, unit=tablet) == Decimal("2400.000")


def test_conversion_goes_through_the_base_not_along_the_chain(paracetamol):
    """A case is 24 boxes, however many links sit between them."""
    _, _, _, pack, case = paracetamol
    assert units.convert(amount=1, source=case, target=pack) == Decimal("24.000")
    assert units.convert(amount=24, source=pack, target=case) == Decimal("1.000")


def test_a_partial_pack_is_reported_as_partial_not_rounded_away(paracetamol):
    """15 tablets is a strip and a half. Rounding to 1 would lose five tablets."""
    _, _, strip, _, _ = paracetamol
    assert units.from_base(base_amount=15, unit=strip) == Decimal("1.500")


def test_units_of_different_products_never_convert(paracetamol):
    _, _, _, pack, _ = paracetamol
    other = product("Amoxicillin", "CAPSULE")
    capsule = unit(other, "CAPSULE", 1, base=True)
    with pytest.raises(UnitError, match="different products"):
        units.convert(amount=1, source=pack, target=capsule)


# ---------------------------------------------------------------------------
# Splitting — approved per product, never per transaction
# ---------------------------------------------------------------------------


def test_a_tablet_may_not_be_split_unless_the_product_says_so(paracetamol):
    """The safe default. A score line is not authority to split."""
    _, tablet, _, _, _ = paracetamol
    with pytest.raises(UnitError, match="dispensed whole only"):
        units.validate(amount="0.5", unit=tablet)


def test_a_product_approved_for_halves_accepts_a_half(paracetamol):
    p = product("Warfarin", divisibility=2)
    tablet = unit(p, "TABLET", 1, base=True)
    assert units.validate(amount="0.5", unit=tablet) == Decimal("0.500")


def test_a_product_approved_for_halves_still_refuses_a_third(paracetamol):
    p = product("Warfarin", divisibility=2)
    tablet = unit(p, "TABLET", 1, base=True)
    with pytest.raises(UnitError, match="halves"):
        units.validate(amount="0.333", unit=tablet)


def test_quarters_are_allowed_when_the_product_is_approved_for_them():
    p = product("Bisoprolol", divisibility=4)
    tablet = unit(p, "TABLET", 1, base=True)
    assert units.validate(amount="0.25", unit=tablet) == Decimal("0.250")
    with pytest.raises(UnitError, match="1/4"):
        units.validate(amount="0.3", unit=tablet)


def test_the_refusal_explains_itself_when_the_catalog_says_why():
    """A counter told only 'invalid' tries again; told the reason, it stops."""
    p = product(
        "Omeprazole",
        form="CAPSULE",
        note="Enteric-coated — splitting destroys the coating and doses it all at once.",
    )
    capsule = unit(p, "CAPSULE", 1, base=True)
    with pytest.raises(UnitError, match="Enteric-coated"):
        units.validate(amount="0.5", unit=capsule)


def test_half_a_box_is_refused_because_it_is_not_a_thing(paracetamol):
    """Half a box of 100 means 50 tablets, and the person meant one of the two."""
    _, _, _, pack, _ = paracetamol
    with pytest.raises(UnitError, match="only be sold whole"):
        units.validate(amount="0.5", unit=pack)


def test_whole_quantities_pass_at_every_level(paracetamol):
    _, tablet, strip, pack, case = paracetamol
    for u in (tablet, strip, pack, case):
        assert units.validate(amount=3, unit=u) == Decimal("3.000")


def test_nothing_is_not_a_quantity(paracetamol):
    _, tablet, _, _, _ = paracetamol
    for bad in (0, -1):
        with pytest.raises(UnitError, match="more than nothing"):
            units.validate(amount=bad, unit=tablet)


def test_a_value_that_is_not_a_number_is_refused(paracetamol):
    _, tablet, _, _, _ = paracetamol
    with pytest.raises(UnitError, match="not a quantity"):
        units.validate(amount="two", unit=tablet)


# ---------------------------------------------------------------------------
# The database keeps the chain coherent
# ---------------------------------------------------------------------------


def test_a_product_cannot_have_two_base_units(paracetamol):
    """Without one defined base, 'which unit did they mean' answers differently
    depending on row order."""
    from django.db.utils import IntegrityError

    p, *_ = paracetamol
    with pytest.raises(IntegrityError):
        unit(p, "CAPSULE", 1, base=True)


def test_the_base_unit_measures_one_of_itself():
    from django.db.utils import IntegrityError

    p = product()
    with pytest.raises(IntegrityError):
        unit(p, "TABLET", 10, base=True)


def test_a_unit_cannot_contain_nothing():
    from django.db.utils import IntegrityError

    p = product()
    with pytest.raises(IntegrityError):
        unit(p, "PACK", 0)


def test_every_product_got_a_base_unit_from_the_migration():
    """The back-fill is what makes existing quantities correct by definition."""
    p = product("Ibuprofen", "SYRUP")
    # A product created after the migration has none until one is recorded;
    # what the migration guarantees is that nothing pre-existing was left bare.
    assert p.base_unit is None
    unit(p, "BOTTLE", 1, base=True)
    p.refresh_from_db()
    assert p.base_unit is not None
    assert p.base_unit.code == "BOTTLE"
