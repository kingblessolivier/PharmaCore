"""Catalog engines: safety screening, price resolution, substitution.

Each pins a model that carried complete data and was read by nothing — a drug
interaction with a severity and management advice that never reached a
pharmacist, a price list that governed no sale, and a substitute never offered
at an empty shelf.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog import dur, pricing, substitution
from apps.catalog.models import (
    ActiveIngredient,
    PriceList,
    Product,
    ProductContraindication,
    ProductIngredient,
    ProductInteraction,
    ProductPrice,
    ProductSubstitute,
)
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch, PharmacyProduct
from django.utils import timezone

pytestmark = pytest.mark.django_db


def today() -> date:
    """The same clock the product reads, at the moment it is asked.

    This was `TODAY = date.today()` evaluated once at module import, which is
    wrong twice over: it is the operating system's date rather than Django's
    (the two differ on a UTC server — see D22), and it freezes. The suite takes
    five minutes, so a run starting at 23:59 asserted against yesterday while the
    code under test had already moved on, and `days_to_expiry == 30` came back
    29. That is a real failure of the test, not of the product.
    """
    return timezone.localdate()


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Pharmacy", type="RETAIL")


def product(name, strength="500mg"):
    return Product.objects.create(generic_name=name, strength=strength)


def ingredient(name):
    return ActiveIngredient.objects.create(name=name)


def contains(prod, ing):
    return ProductIngredient.objects.create(product=prod, ingredient=ing)


def stock(org, prod, qty, *, days=365, number="B1"):
    return InventoryBatch.objects.create(
        organization=org,
        product=prod,
        batch_number=number,
        expiry_date=today() + timedelta(days=days),
        quantity_available=qty,
        status=InventoryBatch.Status.ACTIVE,
    )


# ---------------------------------------------------------------------------
# C1/C2 — drug utilisation review
# ---------------------------------------------------------------------------


def test_an_interacting_pair_in_one_basket_is_caught():
    """The data existed with severity and management advice; nothing read it."""
    warfarin = ingredient("Warfarin")
    aspirin = ingredient("Aspirin")
    a, b = product("Warfarin", "5mg"), product("Aspirin", "300mg")
    contains(a, warfarin)
    contains(b, aspirin)
    ProductInteraction.objects.create(
        ingredient_a=warfarin,
        ingredient_b=aspirin,
        severity=ProductInteraction.Severity.MAJOR,
        effect="Markedly increased bleeding risk.",
        management="Avoid; if unavoidable, monitor INR closely.",
    )

    result = dur.screen_basket(product_ids=[a.pk, b.pk])

    assert not result.is_clear
    assert result.worst == "MAJOR"
    assert result.blocking, "a major interaction needs a reason before dispensing"
    finding = next(f for f in result.findings if f.kind == "INTERACTION")
    assert "bleeding" in finding.detail
    assert "INR" in finding.management


def test_interactions_are_matched_on_ingredients_not_product_names():
    """Two brands of the same pair must still be caught."""
    warfarin, aspirin = ingredient("Warfarin"), ingredient("Aspirin")
    brand_a = product("Coumadin", "5mg")
    brand_b = product("Disprin", "300mg")
    contains(brand_a, warfarin)
    contains(brand_b, aspirin)
    ProductInteraction.objects.create(
        ingredient_a=warfarin, ingredient_b=aspirin, severity=ProductInteraction.Severity.MAJOR
    )

    assert dur.screen_basket(product_ids=[brand_a.pk, brand_b.pk]).worst == "MAJOR"


def test_a_single_product_containing_both_actives_is_not_an_interaction():
    """That is a formulation someone chose, not two medicines colliding."""
    a, b = ingredient("Amoxicillin"), ingredient("Clavulanic acid")
    combo = product("Co-amoxiclav", "625mg")
    contains(combo, a)
    contains(combo, b)
    ProductInteraction.objects.create(
        ingredient_a=a, ingredient_b=b, severity=ProductInteraction.Severity.MODERATE
    )

    assert dur.screen_basket(product_ids=[combo.pk]).is_clear


def test_duplicate_therapy_is_flagged():
    """Two brands, one active — the usual way a dose silently doubles."""
    para = ingredient("Paracetamol")
    panadol = product("Panadol", "500mg")
    generic = product("Paracetamol", "500mg")
    contains(panadol, para)
    contains(generic, para)

    result = dur.screen_basket(product_ids=[panadol.pk, generic.pk])
    finding = next(f for f in result.findings if f.kind == "DUPLICATE")
    assert finding.severity == "MAJOR"
    assert len(finding.products) == 2


def test_a_contraindication_is_raised_against_a_recorded_condition():
    drug = product("Ibuprofen", "400mg")
    ProductContraindication.objects.create(
        product=drug,
        condition="Peptic ulcer",
        severity=ProductContraindication.Severity.CONTRAINDICATED,
        message="Risk of gastrointestinal bleeding.",
    )

    result = dur.screen_basket(product_ids=[drug.pk], conditions=["peptic ulcer"])
    assert result.worst == "CONTRAINDICATED"
    assert "bleeding" in result.findings[0].detail


def test_a_contraindication_for_an_unrecorded_condition_is_not_raised():
    """Warning on everything is the same as warning on nothing."""
    drug = product("Ibuprofen", "400mg")
    ProductContraindication.objects.create(
        product=drug, condition="Peptic ulcer", severity="CONTRAINDICATED"
    )
    assert dur.screen_basket(product_ids=[drug.pk], conditions=["asthma"]).is_clear


def test_a_clean_basket_is_clear():
    a, b = product("Amoxicillin"), product("Vitamin C")
    contains(a, ingredient("Amoxicillin"))
    contains(b, ingredient("Ascorbic acid"))
    screening = dur.screen_basket(product_ids=[a.pk, b.pk])
    assert screening.is_clear
    assert screening.as_dict()["requires_override"] is False


# ---------------------------------------------------------------------------
# C3 — price lists actually govern the price
# ---------------------------------------------------------------------------


def test_an_active_price_list_beats_the_pharmacy_price(org):
    """The list governed nothing before — the till read `retail_price` alone."""
    drug = product("Amoxicillin")
    PharmacyProduct.objects.create(
        organization=org, product=drug, retail_price=Decimal("1000"), is_active=True
    )
    promo = PriceList.objects.create(name="August promo", list_type=PriceList.ListType.RETAIL)
    ProductPrice.objects.create(price_list=promo, product=drug, unit_price=Decimal("800"))

    resolved = pricing.resolve(product=drug, organization=org)
    assert resolved.unit_price == Decimal("800")
    assert resolved.source == "PRICE_LIST"
    assert resolved.price_list_name == "August promo"


def test_without_a_list_the_pharmacy_price_still_applies(org):
    """A pharmacy that never adopted price lists keeps trading exactly as before."""
    drug = product("Amoxicillin")
    PharmacyProduct.objects.create(
        organization=org, product=drug, retail_price=Decimal("1000"), is_active=True
    )
    resolved = pricing.resolve(product=drug, organization=org)
    assert resolved.unit_price == Decimal("1000")
    assert resolved.source == "PHARMACY"


def test_an_out_of_date_list_does_not_apply(org):
    drug = product("Amoxicillin")
    PharmacyProduct.objects.create(
        organization=org, product=drug, retail_price=Decimal("1000"), is_active=True
    )
    from django.utils import timezone

    lapsed = PriceList.objects.create(
        name="July promo",
        effective_from=timezone.now() - timedelta(days=60),
        effective_to=timezone.now() - timedelta(days=1),
    )
    ProductPrice.objects.create(price_list=lapsed, product=drug, unit_price=Decimal("500"))

    assert pricing.resolve(product=drug, organization=org).unit_price == Decimal("1000")


def test_a_quantity_break_applies_only_at_its_quantity(org):
    drug = product("Amoxicillin")
    lst = PriceList.objects.create(name="Standard")
    ProductPrice.objects.create(price_list=lst, product=drug, unit_price=Decimal("1000"))
    ProductPrice.objects.create(
        price_list=lst, product=drug, unit_price=Decimal("700"), min_quantity=50
    )

    assert pricing.resolve(product=drug, organization=org, quantity=10).unit_price == Decimal(
        "1000"
    )
    assert pricing.resolve(product=drug, organization=org, quantity=50).unit_price == Decimal("700")


def test_the_lowest_applicable_price_wins(org):
    """A promotion that charged more than the shelf price is a bug customers spot."""
    drug = product("Amoxicillin")
    standard = PriceList.objects.create(name="Standard")
    promo = PriceList.objects.create(name="Promo")
    ProductPrice.objects.create(price_list=standard, product=drug, unit_price=Decimal("1000"))
    ProductPrice.objects.create(price_list=promo, product=drug, unit_price=Decimal("850"))

    assert pricing.resolve(product=drug, organization=org).unit_price == Decimal("850")


def test_coverage_reports_what_is_falling_back(org):
    priced, unpriced = product("Priced"), product("Unpriced")
    for p in (priced, unpriced):
        PharmacyProduct.objects.create(
            organization=org, product=p, retail_price=Decimal("100"), is_active=True
        )
    lst = PriceList.objects.create(name="Standard")
    ProductPrice.objects.create(price_list=lst, product=priced, unit_price=Decimal("90"))

    cov = pricing.coverage(organization=org)
    assert cov["products_stocked"] == 2
    assert cov["priced_by_list"] == 1
    assert cov["falling_back"] == 1


# ---------------------------------------------------------------------------
# C4 — substitutes at an empty shelf
# ---------------------------------------------------------------------------


def test_only_substitutes_actually_in_stock_are_offered(org):
    """A suggestion that is also out of stock sends the counter on a second search."""
    wanted = product("Brand A")
    in_stock = product("Generic A")
    out_of_stock = product("Generic B")
    ProductSubstitute.objects.create(
        product=wanted,
        substitute_product=in_stock,
        substitute_type=ProductSubstitute.SubstituteType.GENERIC_EQUIVALENT,
    )
    ProductSubstitute.objects.create(
        product=wanted,
        substitute_product=out_of_stock,
        substitute_type=ProductSubstitute.SubstituteType.GENERIC_EQUIVALENT,
    )
    stock(org, in_stock, 40)

    options = substitution.options_for(product=wanted, organization=org)
    assert [o.product_id for o in options] == [in_stock.pk]
    assert options[0].available == 40


def test_expired_stock_never_counts_as_an_available_substitute(org):
    wanted, alt = product("Brand A"), product("Generic A")
    ProductSubstitute.objects.create(product=wanted, substitute_product=alt)
    stock(org, alt, 40, days=-1)

    assert substitution.options_for(product=wanted, organization=org) == []


def test_generic_equivalents_are_separated_from_therapeutic_alternatives(org):
    """One is usually the pharmacist's call; the other is usually the prescriber's."""
    wanted = product("Brand A")
    generic = product("Generic A")
    alternative = product("Different drug")
    ProductSubstitute.objects.create(
        product=wanted,
        substitute_product=generic,
        substitute_type=ProductSubstitute.SubstituteType.GENERIC_EQUIVALENT,
    )
    ProductSubstitute.objects.create(
        product=wanted,
        substitute_product=alternative,
        substitute_type=ProductSubstitute.SubstituteType.THERAPEUTIC_ALTERNATIVE,
    )
    stock(org, generic, 10)
    stock(org, alternative, 10, number="B2")

    payload = substitution.suggest(product=wanted, organization=org)
    assert [g["product"] for g in payload["generic_equivalents"]] == [generic.pk]
    assert [a["product"] for a in payload["therapeutic_alternatives"]] == [alternative.pk]


def test_a_product_with_no_substitutes_returns_nothing(org):
    assert substitution.suggest(product=product("Lonely"), organization=org)["has_options"] is False
