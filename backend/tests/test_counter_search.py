"""Finding a product by typing, because most pharmacies here have no barcodes.

The till could only resolve an exact barcode. Type "amox" and it answered
"Nothing matches amox." — so without barcode labelling nothing could be sold at
all. Searching by name is not a lesser fallback to scanning: it is how a
pharmacist works when the box is unlabelled, when the customer describes a
symptom, and when the scanner is broken.

Ranking is most of the value here, so most of these test the order rather than
the membership. A cashier with a queue reads the first two rows.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import (
    ActiveIngredient,
    Product,
    ProductBarcode,
    ProductIngredient,
)
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail import counter
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def stock_it(org, product, qty=50, *, price="1000", days=365):
    """List a product at this pharmacy and put some on the shelf."""
    PharmacyProduct.objects.create(
        organization=org, product=product, retail_price=Decimal(price), is_active=True
    )
    if qty:
        InventoryBatch.objects.create(
            organization=org,
            product=product,
            batch_number=f"B{InventoryBatch.objects.count()}",
            expiry_date=timezone.localdate() + timedelta(days=days),
            quantity_available=qty,
            status=InventoryBatch.Status.ACTIVE,
            wholesale_cost=Decimal("600"),
        )
    return product


def drug(generic, *, brand="", strength="500mg"):
    return Product.objects.create(generic_name=generic, brand_name=brand, strength=strength)


def names(matches):
    return [m.product.generic_name for m in matches]


# --------------------------------------------------------------------------- #
# The defect itself
# --------------------------------------------------------------------------- #


def test_typing_part_of_a_name_finds_the_medicine(org):
    """Before this, the only answer to "amox" was "Nothing matches amox."."""
    stock_it(org, drug("Amoxicillin"))
    stock_it(org, drug("Paracetamol"))

    assert names(counter.search_products(organization=org, query="amox")) == ["Amoxicillin"]


def test_a_brand_name_finds_the_generic(org):
    """Customers ask for Panadol; the shelf label says paracetamol."""
    stock_it(org, drug("Paracetamol", brand="Panadol"))
    assert names(counter.search_products(organization=org, query="panadol")) == ["Paracetamol"]


def test_an_ingredient_finds_products_containing_it(org):
    """ "Something with amoxicillin in it" is a real counter question."""
    combo = stock_it(org, drug("Co-amoxiclav", strength="625mg"))
    amox = ActiveIngredient.objects.create(name="Amoxicillin")
    ProductIngredient.objects.create(product=combo, ingredient=amox)

    assert "Co-amoxiclav" in names(counter.search_products(organization=org, query="amoxicill"))


def test_search_is_case_and_position_insensitive(org):
    stock_it(org, drug("Amoxicillin"))
    for query in ("AMOX", "amox", "Amox", "oxicill"):
        assert names(counter.search_products(organization=org, query=query)) == ["Amoxicillin"]


# --------------------------------------------------------------------------- #
# Ranking — where the value is
# --------------------------------------------------------------------------- #


def test_a_name_that_starts_with_the_query_comes_first(org):
    """A mid-word hit is rarely the one they meant."""
    stock_it(org, drug("Cetirizine"))
    stock_it(org, drug("Paracetamol"))

    assert names(counter.search_products(organization=org, query="cet"))[0] == "Cetirizine"


def test_stock_breaks_the_tie(org):
    """A perfect match you cannot sell is not a match."""
    stock_it(org, drug("Amoxicillin", strength="250mg"), qty=0)
    stock_it(org, drug("Amoxicillin", strength="500mg"), qty=40)

    first = counter.search_products(organization=org, query="amox")[0]
    assert first.on_hand == 40


def test_out_of_stock_is_still_offered_rather_than_hidden(org):
    """The cashier needs to know it exists to offer a substitute or order it."""
    stock_it(org, drug("Amoxicillin"), qty=0)
    matches = counter.search_products(organization=org, query="amox")
    assert len(matches) == 1
    assert matches[0].on_hand == 0


def test_expired_stock_does_not_count_as_on_hand(org):
    stock_it(org, drug("Amoxicillin"), qty=40, days=-1)
    assert counter.search_products(organization=org, query="amox")[0].on_hand == 0


def test_the_price_comes_from_the_same_resolver_as_the_scanner(org):
    stock_it(org, drug("Amoxicillin"), price="1500")
    match = counter.search_products(organization=org, query="amox")[0]
    assert match.unit_price == Decimal("1500")
    assert match.price_source == "PHARMACY"


# --------------------------------------------------------------------------- #
# Scope and guards
# --------------------------------------------------------------------------- #


def test_only_what_this_pharmacy_sells_is_offered(org):
    """The national catalogue holds thousands this branch never carried."""
    stock_it(org, drug("Amoxicillin"))
    Product.objects.create(generic_name="Amoxicillin syrup", strength="125mg")  # not listed

    assert names(counter.search_products(organization=org, query="amox")) == ["Amoxicillin"]


def test_another_pharmacys_listing_is_not_offered(org):
    other = Organization.objects.create(name="Nyamirambo Pharmacy", type="RETAIL")
    stock_it(other, drug("Amoxicillin"))
    assert counter.search_products(organization=org, query="amox") == []


def test_one_letter_is_a_keystroke_not_a_search(org):
    stock_it(org, drug("Amoxicillin"))
    assert counter.search_products(organization=org, query="a") == []
    assert counter.search_products(organization=org, query="") == []


def test_the_result_set_is_capped(org):
    for n in range(20):
        stock_it(org, drug(f"Amoxicillin variant {n}"))
    assert len(counter.search_products(organization=org, query="amox")) == counter.SEARCH_LIMIT


# --------------------------------------------------------------------------- #
# Telling a scanner from fingers
# --------------------------------------------------------------------------- #


def test_a_barcode_is_recognised_as_one():
    assert counter.looks_like_a_barcode("5901234123457")
    assert counter.looks_like_a_barcode("12345678")


def test_a_typed_name_is_not_mistaken_for_a_barcode():
    for typed in ("amox", "Panadol", "500mg", "1234567", "paracetamol 500"):
        assert not counter.looks_like_a_barcode(typed), typed


# --------------------------------------------------------------------------- #
# Over HTTP
# --------------------------------------------------------------------------- #


@pytest.fixture
def cashier(org):
    user = User.objects.create_user(username="aline", password="pw", organization=org)
    user.roles.add(Role.objects.get(code="CASHIER"))
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_the_endpoint_answers_a_typed_query(cashier, org):
    stock_it(org, drug("Amoxicillin"))
    resp = cashier.get(f"/api/retail/counter/search/?organization={org.pk}&q=amox")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    row = body["results"][0]
    assert row["label"] == "Amoxicillin 500mg"
    assert row["on_hand"] == 50
    assert row["units"] == 1
    assert body["exact"] is None


def test_a_scanned_barcode_resolves_in_the_same_call(cashier, org):
    """The scanner path must not need a second round trip."""
    product = stock_it(org, drug("Amoxicillin"))
    ProductBarcode.objects.create(
        product=product, barcode="5901234123457", packaging_level="CASE", units_per_level=24
    )
    resp = cashier.get(f"/api/retail/counter/search/?organization={org.pk}&q=5901234123457")
    assert resp.status_code == 200
    exact = resp.json()["exact"]
    assert exact is not None
    assert exact["product"] == product.pk
    assert exact["units"] == 24, "a carton barcode must add the carton"


def test_a_query_matching_nothing_is_an_empty_list_not_an_error(cashier, org):
    """404 on a half-typed word makes the till look broken while someone types."""
    resp = cashier.get(f"/api/retail/counter/search/?organization={org.pk}&q=zzzz")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_a_cashier_may_search_but_a_driver_may_not(org):
    driver = User.objects.create_user(username="moses", password="pw", organization=org)
    driver.roles.add(Role.objects.get(code="DRIVER"))
    client = APIClient()
    client.force_authenticate(user=driver)
    resp = client.get(f"/api/retail/counter/search/?organization={org.pk}&q=amox")
    assert resp.status_code == 403
