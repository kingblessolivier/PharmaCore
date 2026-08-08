"""One pharmacy's pricing must not reach another's till.

`PriceList` and `POSPromotion` carried no organization, so every active list and
every coupon applied to every pharmacy in the system. Before this fix, Remera
creating a weekend promotion repriced Nyamirambo — a different shop, and a
competitor — and the depot as well.

Multi-tenancy here is an `organization` FK plus `organizations_visible_to`. A
model without the FK is global by construction, and no amount of view-layer
scoping fixes it, because the leak is in the query that prices the sale.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog import pricing
from apps.catalog.models import PriceList, Product, ProductPrice
from apps.iam.models import Organization
from apps.inventory.models import PharmacyProduct
from apps.retail.counter import active_promotions, evaluate_promotion
from apps.retail.models import POSPromotion, Sale

pytestmark = pytest.mark.django_db

TODAY = date.today()


@pytest.fixture
def shops():
    return {
        "remera": Organization.objects.create(name="Remera Pharmacy", type="RETAIL"),
        "nyamirambo": Organization.objects.create(name="Nyamirambo Pharmacy", type="RETAIL"),
        "depot": Organization.objects.create(name="Kigali Depot", type="DEPOT"),
    }


@pytest.fixture
def drug(shops):
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    for org, price in ((shops["remera"], "1000"), (shops["nyamirambo"], "1200"),
                       (shops["depot"], "700")):
        PharmacyProduct.objects.create(
            organization=org, product=product, retail_price=Decimal(price), is_active=True
        )
    return product


# ---------------------------------------------------------------------------
# Price lists
# ---------------------------------------------------------------------------


def test_a_promo_at_one_pharmacy_leaves_the_others_alone(shops, drug):
    """The exact scenario from the audit — it changed all three prices."""
    promo = PriceList.objects.create(
        name="Remera weekend promo",
        organization=shops["remera"],
        list_type=PriceList.ListType.RETAIL,
    )
    ProductPrice.objects.create(price_list=promo, product=drug, unit_price=Decimal("650"))

    assert pricing.resolve(product=drug, organization=shops["remera"]).unit_price == Decimal("650")
    assert pricing.resolve(
        product=drug, organization=shops["nyamirambo"]
    ).unit_price == Decimal("1200")
    assert pricing.resolve(product=drug, organization=shops["depot"]).unit_price == Decimal("700")


def test_a_group_wide_list_still_applies_everywhere(shops, drug):
    """Null organization is HQ setting one price across the chain — a real case."""
    group = PriceList.objects.create(name="Group standard", organization=None)
    ProductPrice.objects.create(price_list=group, product=drug, unit_price=Decimal("900"))

    for key in ("remera", "nyamirambo", "depot"):
        assert pricing.resolve(product=drug, organization=shops[key]).unit_price == Decimal("900")


def test_a_branch_list_beats_the_group_list_when_cheaper(shops, drug):
    group = PriceList.objects.create(name="Group standard", organization=None)
    ProductPrice.objects.create(price_list=group, product=drug, unit_price=Decimal("900"))
    local = PriceList.objects.create(name="Remera promo", organization=shops["remera"])
    ProductPrice.objects.create(price_list=local, product=drug, unit_price=Decimal("750"))

    assert pricing.resolve(product=drug, organization=shops["remera"]).unit_price == Decimal("750")
    assert pricing.resolve(
        product=drug, organization=shops["nyamirambo"]
    ).unit_price == Decimal("900")


def test_coverage_counts_only_this_pharmacys_lists(shops, drug):
    other = PriceList.objects.create(name="Nyamirambo only", organization=shops["nyamirambo"])
    ProductPrice.objects.create(price_list=other, product=drug, unit_price=Decimal("650"))

    remera = pricing.coverage(organization=shops["remera"])
    assert remera["active_lists"] == 0
    assert remera["falling_back"] == 1
    assert pricing.coverage(organization=shops["nyamirambo"])["priced_by_list"] == 1


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


def promo(org, code, **kw):
    return POSPromotion.objects.create(
        organization=org,
        code=code,
        name=f"{code} campaign",
        discount_value=Decimal(kw.get("value", "10")),
        valid_from=TODAY - timedelta(days=1),
        valid_until=TODAY + timedelta(days=30),
        is_active=True,
    )


def test_a_coupon_from_another_branch_is_not_redeemable(shops, drug):
    promo(shops["remera"], "REMERA10")
    sale = Sale.objects.create(organization=shops["nyamirambo"], status=Sale.Status.OPEN)

    outcome = evaluate_promotion(sale=sale, code="REMERA10")
    assert outcome.promotion is None
    assert "No promotion with the code" in outcome.reason


def test_your_own_coupon_is_found(shops, drug):
    """Scoping decides *found or not found*; what it is worth is a separate matter."""
    promo(shops["remera"], "REMERA10")
    sale = Sale.objects.create(organization=shops["remera"], status=Sale.Status.OPEN)
    assert "No promotion with the code" not in evaluate_promotion(
        sale=sale, code="REMERA10"
    ).reason


def test_a_group_wide_coupon_is_found_at_every_branch(shops):
    promo(None, "CHAIN10")
    for n, key in enumerate(("remera", "nyamirambo")):
        sale = Sale.objects.create(
            organization=shops[key], status=Sale.Status.OPEN, sale_number=f"T-{n}"
        )
        assert "No promotion with the code" not in evaluate_promotion(
            sale=sale, code="CHAIN10"
        ).reason


def test_two_branches_may_each_run_the_same_code(shops):
    """`code` was globally unique, so the second branch was refused."""
    promo(shops["remera"], "WEEKEND10")
    promo(shops["nyamirambo"], "WEEKEND10")
    assert POSPromotion.objects.filter(code="WEEKEND10").count() == 2


def test_the_till_only_offers_this_pharmacys_coupons(shops):
    promo(shops["remera"], "REMERA10")
    promo(shops["nyamirambo"], "NYAMI10")
    promo(None, "CHAIN10")

    codes = {p.code for p in active_promotions(organization=shops["remera"])}
    assert codes == {"REMERA10", "CHAIN10"}
