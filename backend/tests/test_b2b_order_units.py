"""A wholesale order says what it is counting in.

A B2B line saying "10" is meaningless on its own: ten cartons and ten tablets
differ by a factor of 2,400, and the depot picking the order has only the
number to go on. Purchase orders learned this in #121; orders to depots were
still dimensionless, so a pharmacy meaning "two cartons" was checked against
availability, priced, and picked as though it had asked for two tablets.

The two things that must hold, and both were broken:

* **availability is decided in base units** — two cartons is 4,800 tablets, and
  a depot holding 10 cannot fill it;
* **money is computed on base units** — the published price is per tablet, so
  pricing two cartons as two tablets is an error of the whole carton.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductUnit
from apps.distribution import marketplace
from apps.distribution.models import OrderItem, StockOrder
from apps.iam.models import Organization, Permission, Role, User
from apps.inventory.models import InventoryBatch
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def depot() -> Organization:
    return Organization.objects.create(name="Kigali Central Depot", type="DEPOT")


@pytest.fixture
def pharmacy() -> Organization:
    return Organization.objects.create(name="Nyarugenge Pharmacy", type="RETAIL")


@pytest.fixture
def product() -> Product:
    """Amoxicillin: a tablet, a box of 100, a carton of 24 boxes."""
    item = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    ProductUnit.objects.create(product=item, code="TABLET", factor_to_base=1, level=0, is_base=True)
    ProductUnit.objects.create(
        product=item, code="BOX", name="Box of 100", factor_to_base=100, level=1
    )
    ProductUnit.objects.create(
        product=item,
        code="CARTON",
        name="Carton of 24 boxes",
        factor_to_base=2400,
        level=2,
        is_purchase_default=True,
    )
    return item


@pytest.fixture
def carton(product: Product) -> ProductUnit:
    return product.units.get(code="CARTON")


def offer(depot: Organization, product: Product, *, qty: int, price: str) -> None:
    """Publish an offer *and* put the stock behind it.

    Availability is the lesser of what is published and what is physically on
    the shelf, so an offer without a batch is offering nothing.
    """
    InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number=f"LOT-{qty}",
        expiry_date=timezone.localdate() + timedelta(days=365),
        quantity_available=Decimal(qty),
        status=InventoryBatch.Status.ACTIVE,
    )
    marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=qty,
        price_per_unit=Decimal(price),
    )


def buyer(pharmacy: Organization) -> APIClient:
    user = User.objects.create_user(
        username="wtbuyer",
        password="x",  # noqa: S106 - test fixture
        organization=pharmacy,
    )
    role, _ = Role.objects.get_or_create(code="BUYER", defaults={"name": "Buyer"})
    for code in ("order.create", "order.approve", "inventory.view"):
        resource, _, action = code.partition(".")
        permission, _ = Permission.objects.get_or_create(
            code=code, defaults={"resource": resource, "action": action}
        )
        role.permissions.add(permission)
    user.roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def place(client: APIClient, depot: Organization, pharmacy: Organization, **line: object):
    """Try to place a one-line order. Returns the response, refusal and all."""
    return client.post(
        "/api/distribution/orders/",
        {
            "depot": depot.pk,
            "retail": pharmacy.pk,
            "items": [line],
            "allow_backorder": False,
        },
        format="json",
    )


def place_ok(client: APIClient, depot: Organization, pharmacy: Organization, **line: object):
    response = place(client, depot, pharmacy, **line)
    assert response.status_code in (200, 201), response.data
    return response


class TestAvailabilityIsDecidedInBaseUnits:
    def test_two_cartons_against_ten_tablets_cannot_be_filled(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        """The bug, stated plainly.

        Two cartons is 4,800 tablets. A depot offering 10 tablets cannot supply
        that — but the "2" was compared against the "10" as though both meant
        tablets, and the order went through.
        """
        offer(depot, product, qty=10, price="1500.00")
        response = place(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=2,
        )
        assert response.status_code == 400, response.data
        assert OrderItem.objects.count() == 0, "4,800 tablets cannot come out of 10"

    def test_two_cartons_against_enough_stock_is_filled(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        offer(depot, product, qty=10_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=2,
        )
        line = OrderItem.objects.get()
        assert line.quantity_ordered == 2, "the order still reads as the buyer placed it"
        assert line.quantity_base == Decimal("4800.000"), "and as the picker must read it"

    def test_a_line_with_no_unit_is_still_read_as_base_units(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        # Every line written before units existed meant base units, and must
        # keep meaning that.
        offer(depot, product, qty=500, price="1500.00")
        place_ok(buyer(pharmacy), depot, pharmacy, product=product.pk, quantity_ordered=10)
        line = OrderItem.objects.get()
        assert line.unit_id is None
        assert line.quantity_base == Decimal("10.000")


class TestMoney:
    def test_two_cartons_cost_what_two_cartons_cost(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        """The money half of the same bug.

        The published price is per tablet. Two cartons is 4,800 tablets, so the
        line is 4,800 × 1,500 = 7,200,000 — not 2 × 1,500 = 3,000, which is
        what multiplying the price by the pack count produced.
        """
        offer(depot, product, qty=10_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=2,
        )
        line = OrderItem.objects.get()
        assert line.line_total == pytest.approx(7_200_000.0)

    def test_the_displayed_unit_price_is_per_carton(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        # A screen showing "2 × RWF 1,500 = RWF 7,200,000" is not readable.
        offer(depot, product, qty=10_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=2,
        )
        line = OrderItem.objects.get()
        assert line.price_per_unit == Decimal("1500.00"), "the published price is untouched"
        assert line.price_per_ordered_unit == Decimal("3600000.00")

    def test_a_base_unit_order_prices_exactly_as_before(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        offer(depot, product, qty=500, price="1500.00")
        place_ok(buyer(pharmacy), depot, pharmacy, product=product.pk, quantity_ordered=10)
        line = OrderItem.objects.get()
        assert line.line_total == pytest.approx(15_000.0)
        assert line.price_per_ordered_unit == Decimal("1500.00")

    def test_the_order_total_follows(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        offer(depot, product, qty=10_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=1,
        )
        assert StockOrder.objects.get().total_amount == pytest.approx(3_600_000.0)


class TestTheLineSaysWhatItMeans:
    def test_the_unit_is_named_on_the_line(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        offer(depot, product, qty=10_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=2,
        )
        line = OrderItem.objects.get()
        assert line.unit_label == "Carton of 24 boxes"
        assert "CARTON" in str(line)

    def test_a_unitless_line_says_nothing_rather_than_guessing(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        offer(depot, product, qty=500, price="1500.00")
        place_ok(buyer(pharmacy), depot, pharmacy, product=product.pk, quantity_ordered=10)
        assert OrderItem.objects.get().unit_label == ""


class TestPartialFillsRespectThePack:
    def test_a_depot_supplies_whole_packs_and_no_more(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        """50,000 tablets is twenty whole cartons and 2,000 loose.

        The loose ones stay on the shelf: a depot does not open a carton to
        top up an order placed in cartons. Without the flooring the line came
        back as "20.833 cartons", which is not a thing anybody can pick.
        """
        offer(depot, product, qty=50_000, price="1500.00")
        place_ok(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=100,
        )
        line = OrderItem.objects.get()
        assert line.quantity_ordered == 20
        assert line.quantity_base == Decimal("48000.000")
        assert line.line_total == pytest.approx(72_000_000.0)

    def test_less_than_one_whole_pack_supplies_nothing(
        self, depot: Organization, pharmacy: Organization, product: Product, carton: ProductUnit
    ) -> None:
        # 2,000 tablets is not a carton, so there is no carton to send.
        offer(depot, product, qty=2_000, price="1500.00")
        response = place(
            buyer(pharmacy),
            depot,
            pharmacy,
            product=product.pk,
            unit=carton.pk,
            quantity_ordered=1,
        )
        assert response.status_code == 400
        assert OrderItem.objects.count() == 0


class TestTheDocumentIsReachableAndGuarded:
    """The order document, and who may open it.

    It has been generated, numbered and hashed on approval all along, and no
    screen could reach it — the same gap purchase orders had. Reaching it is
    only half the fix: the obvious way to link a stored file is its media path,
    which the web server hands to anyone who has the URL, with no login.
    """

    def _approved_order(self, depot: Organization, pharmacy: Organization, product: Product):
        from apps.distribution.services import generate_po_document

        offer(depot, product, qty=50_000, price="1500.00")
        client = buyer(pharmacy)
        place_ok(client, depot, pharmacy, product=product.pk, quantity_ordered=10)
        order = StockOrder.objects.get()
        generate_po_document(order=order, user=User.objects.get(username="wtbuyer"))
        return client, order

    def test_the_order_carries_a_link_to_its_document(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        client, order = self._approved_order(depot, pharmacy, product)
        response = client.get(f"/api/distribution/orders/{order.pk}/")
        assert response.data["document"] is not None
        assert response.data["document"]["doc_number"]

    def test_the_link_is_the_authenticated_endpoint_not_the_raw_file(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        # `/media/…` is served by the web server with no credentials at all.
        client, order = self._approved_order(depot, pharmacy, product)
        url = client.get(f"/api/distribution/orders/{order.pk}/").data["document"]["download_url"]
        assert url.startswith("/api/documents/")
        assert "/media/" not in url

    def test_the_buyer_can_open_it(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        client, order = self._approved_order(depot, pharmacy, product)
        url = client.get(f"/api/distribution/orders/{order.pk}/").data["document"]["download_url"]
        assert client.get(url).status_code == 200

    def test_a_stranger_cannot(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        client, order = self._approved_order(depot, pharmacy, product)
        url = client.get(f"/api/distribution/orders/{order.pk}/").data["document"]["download_url"]

        outsider_org = Organization.objects.create(name="Someone Else", type="RETAIL")
        outsider = User.objects.create_user(
            username="outsider",
            password="x",  # noqa: S106 - test fixture
            organization=outsider_org,
        )
        stranger = APIClient()
        stranger.force_authenticate(user=outsider)
        assert stranger.get(url).status_code in (403, 404)

    def test_nobody_at_all_cannot(
        self, depot: Organization, pharmacy: Organization, product: Product
    ) -> None:
        client, order = self._approved_order(depot, pharmacy, product)
        url = client.get(f"/api/distribution/orders/{order.pk}/").data["document"]["download_url"]
        assert APIClient().get(url).status_code in (401, 403)
