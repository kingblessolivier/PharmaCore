"""Two rules a depot storefront needs to be trusted.

**Order multiples.** A case is not opened to fill an order, so a depot shipping
by the case sells 5 or 10, never 7. Without this a pharmacy places a quantity
the depot cannot pick and both sides discover it on the loading bay.

**Image verification.** An unverified picture is worse than none, because a
buyer trusts it — a wrong photo on a listing sells the wrong medicine. Upload
and verification are separate acts, as they are for batch paperwork.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.distribution.marketplace import decide_line
from apps.distribution.models import DepotProductListing
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def depot():
    return Organization.objects.create(name="Kigali Central Depot", type="DEPOT")


@pytest.fixture
def buyer():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


@pytest.fixture
def product():
    return Product.objects.create(generic_name="Paracetamol", strength="500mg")


def listing(depot, product, *, offered=1000, multiple=1, minimum=1):
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number="B1",
        expiry_date=timezone.localdate() + timedelta(days=365),
        quantity_available=Decimal(offered),
        status=InventoryBatch.Status.ACTIVE,
    )
    return DepotProductListing.objects.create(
        depot=depot,
        product=product,
        offered_qty=offered,
        price_per_unit=Decimal("100"),
        is_published=True,
        min_order_qty=minimum,
        order_multiple=multiple,
    )


# ---------------------------------------------------------------------------
# Order multiples
# ---------------------------------------------------------------------------


def test_a_depot_selling_singly_is_unaffected(depot, buyer, product):
    listing(depot, product, multiple=1)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=7)
    assert decision.fulfillable == 7


def test_an_order_is_rounded_down_to_a_whole_multiple(depot, buyer, product):
    """Seven of something sold in fives ships five."""
    listing(depot, product, multiple=5)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=7)
    assert decision.fulfillable == 5


def test_the_remainder_becomes_demand_rather_than_vanishing(depot, buyer, product):
    """The two the depot could not ship is a signal, not a rounding loss."""
    listing(depot, product, multiple=5)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=7)
    assert decision.backordered == 2


def test_an_exact_multiple_ships_whole(depot, buyer, product):
    listing(depot, product, multiple=5)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=20)
    assert decision.fulfillable == 20
    assert decision.backordered == 0


def test_a_quantity_below_the_minimum_is_refused_by_the_minimum(depot, buyer, product):
    """The minimum is the more fundamental refusal, so it answers first."""
    listing(depot, product, multiple=10, minimum=10)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=9)
    assert decision.fulfillable == 0
    assert "minimum order is 10" in decision.note


def test_rounding_below_the_minimum_ships_nothing_and_says_why(depot, buyer, product):
    """Eight clears a minimum of six, but rounds to zero in multiples of ten —
    so the refusal has to name the multiple, not the minimum."""
    listing(depot, product, multiple=10, minimum=6)
    decision = decide_line(depot=depot, buyer=buyer, product=product, quantity=8)
    assert decision.fulfillable == 0
    assert "multiples of 10" in decision.note
    assert "Kigali Central Depot" in decision.note


# ---------------------------------------------------------------------------
# Image verification
# ---------------------------------------------------------------------------


@pytest.fixture
def shelf(buyer, product):
    return PharmacyProduct.objects.create(
        organization=buyer,
        product=product,
        retail_price=Decimal("120"),
        is_active=True,
        image_url="https://example.test/paracetamol.jpg",
    )


def test_an_uploaded_photo_is_not_trusted_until_someone_checks_it(shelf):
    assert shelf.image_url
    assert shelf.image_is_trusted is False


def test_verifying_makes_it_showable(shelf, buyer):
    checker = User.objects.create_user(username="pharmacist", password="pw", organization=buyer)
    shelf.image_verified_by = checker
    shelf.image_verified_at = timezone.now()
    shelf.save()

    shelf.refresh_from_db()
    assert shelf.image_is_trusted is True


def test_changing_the_photo_clears_the_verification(shelf, buyer):
    """Otherwise the check is a one-off: verify a correct picture, swap it for
    anything later, and the tick stays."""
    checker = User.objects.create_user(username="pharmacist", password="pw", organization=buyer)
    shelf.image_verified_by = checker
    shelf.image_verified_at = timezone.now()
    shelf.save()

    shelf.image_url = "https://example.test/something-else.jpg"
    shelf.save()

    shelf.refresh_from_db()
    assert shelf.image_verified_at is None
    assert shelf.image_verified_by is None
    assert shelf.image_is_trusted is False


def test_saving_without_touching_the_photo_keeps_the_verification(shelf, buyer):
    checker = User.objects.create_user(username="pharmacist", password="pw", organization=buyer)
    shelf.image_verified_by = checker
    shelf.image_verified_at = timezone.now()
    shelf.save()

    shelf.retail_price = Decimal("130")
    shelf.save()

    shelf.refresh_from_db()
    assert shelf.image_is_trusted is True, "a price change is not a photo change"


def test_a_row_with_no_photo_is_never_trusted(buyer, product):
    bare = PharmacyProduct.objects.create(
        organization=buyer, product=product, retail_price=Decimal("120"), is_active=True
    )
    bare.image_verified_at = timezone.now()
    bare.save()
    assert bare.image_is_trusted is False


def test_the_same_rule_governs_a_depot_storefront(depot, product):
    row = listing(depot, product)
    row.image_url = "https://example.test/case.jpg"
    row.save()
    assert row.image_is_trusted is False

    row.image_verified_at = timezone.now()
    row.save()
    assert row.image_is_trusted is True

    row.image_url = "https://example.test/other.jpg"
    row.save()
    assert row.image_is_trusted is False
