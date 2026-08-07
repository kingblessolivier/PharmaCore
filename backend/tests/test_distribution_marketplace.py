"""The wholesale marketplace: what a depot offers, what it withholds, and the
demand it cannot meet.

These pin the behaviours the audit found missing entirely — the storefront
governed nothing, the depot could ship expired stock, and unmet demand was thrown
away instead of being turned into an import.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.distribution import demand as demand_engine
from apps.distribution import fieldsales, marketplace, returns
from apps.distribution.models import (
    BackorderLine,
    CustomerReturn,
    CustomerReturnLine,
    SalesRepresentative,
    StockOrder,
    TenderContract,
    VanStock,
)
from apps.distribution.services import approve_and_allocate
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch
from apps.procurement.models import PurchaseRequisition

pytestmark = pytest.mark.django_db

TODAY = date.today()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def depot():
    return Organization.objects.create(name="Kigali Central Depot", type="DEPOT")


@pytest.fixture
def retail():
    return Organization.objects.create(
        name="Gasabo Pharmacy", type="RETAIL", province="KIGALI", district="GASABO"
    )


@pytest.fixture
def product():
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


def stock(depot, product, qty, *, expiry_days=365, batch="B1", reserved=0):
    return InventoryBatch.objects.create(
        organization=depot,
        product=product,
        batch_number=batch,
        expiry_date=TODAY + timedelta(days=expiry_days),
        quantity_available=qty,
        quantity_reserved=reserved,
        status=InventoryBatch.Status.ACTIVE,
    )


# ---------------------------------------------------------------------------
# D1/D2 — availability is the smaller of what is offered and what is held
# ---------------------------------------------------------------------------


def test_availability_is_capped_by_physical_stock(depot, retail, product):
    """A depot may publish 100 while holding 30. It cannot sell 100."""
    stock(depot, product, 30)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("2500")
    )

    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.available == 30
    assert avail.physical_free == 30
    assert avail.reason == "limited by stock on hand"


def test_buffer_is_held_back_from_the_marketplace(depot, retail, product):
    """The buffer is the depot's own reserve — buyers may never reach it."""
    stock(depot, product, 100)
    marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=100,
        buffer_qty=40,
        price_per_unit=Decimal("2500"),
    )

    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.available == 60, "40 units are reserved for the depot itself"


def test_withdrawn_listing_is_invisible_even_with_stock(depot, retail, product):
    """A wholesaler may hold stock and choose to show none of it."""
    stock(depot, product, 500)
    marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=500,
        price_per_unit=Decimal("2500"),
        is_published=False,
    )

    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.is_listed is False
    assert avail.available == 0
    assert avail.reason == "withdrawn from sale by the depot"
    assert marketplace.storefront(depot=depot, buyer=retail) == []


def test_reserved_stock_is_not_available(depot, retail, product):
    stock(depot, product, 100, reserved=70)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("2500")
    )
    assert marketplace.availability(depot=depot, product=product, buyer=retail).available == 30


def test_expired_stock_is_never_available(depot, retail, product):
    stock(depot, product, 100, expiry_days=-1)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("2500")
    )
    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.physical_free == 0
    assert avail.available == 0


def test_segment_restricts_who_may_buy(depot, product):
    """A depot can offer to one district only."""
    stock(depot, product, 100)
    marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=100,
        price_per_unit=Decimal("2500"),
        customer_segment="GASABO",
    )
    inside = Organization.objects.create(name="In", type="RETAIL", district="GASABO")
    outside = Organization.objects.create(name="Out", type="RETAIL", district="HUYE")

    assert marketplace.availability(depot=depot, product=product, buyer=inside).is_listed
    blocked = marketplace.availability(depot=depot, product=product, buyer=outside)
    assert blocked.is_listed is False
    assert "restricted" in blocked.reason


def test_coverage_reports_what_is_held_back_and_oversold(depot, product):
    other = Product.objects.create(generic_name="Paracetamol", strength="500mg")
    stock(depot, product, 10)
    stock(depot, other, 50, batch="B2")
    marketplace.publish(
        depot=depot, product=product, offered_qty=999, price_per_unit=Decimal("100")
    )
    marketplace.publish(
        depot=depot,
        product=other,
        offered_qty=50,
        price_per_unit=Decimal("100"),
        is_published=False,
    )

    cov = marketplace.coverage(depot=depot)
    assert cov["products_held"] == 2
    assert cov["published"] == 1
    assert cov["withheld"] == 1
    assert len(cov["oversold"]) == 1
    assert cov["oversold"][0]["offered"] == 999
    assert cov["oversold"][0]["sellable"] == 10


# ---------------------------------------------------------------------------
# D3 — expired stock must never be reserved
# ---------------------------------------------------------------------------


def test_depot_never_reserves_expired_stock(depot, retail, product):
    """FEFO orders by expiry, so without a guard expired stock is picked *first*."""
    stock(depot, product, 100, expiry_days=-5, batch="EXPIRED")
    stock(depot, product, 100, expiry_days=200, batch="GOOD")

    order = StockOrder.objects.create(depot=depot, retail=retail, order_number="PO-X1")
    item = order.items.create(product=product, quantity_ordered=50, price_per_unit=Decimal("100"))

    approve_and_allocate(order=order, user=None)

    reserved_batches = {r.batch.batch_number for r in order.reservations.all()}
    assert reserved_batches == {"GOOD"}, "expired stock must never be allocated"
    item.refresh_from_db()
    assert order.reservations.count() == 1


# ---------------------------------------------------------------------------
# D4 — demand the depot cannot meet becomes an import
# ---------------------------------------------------------------------------


def test_short_line_is_split_into_shipment_and_backorder(depot, retail, product):
    stock(depot, product, 30)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("2500")
    )

    decision = marketplace.decide_line(depot=depot, buyer=retail, product=product, quantity=80)
    assert decision.fulfillable == 30
    assert decision.backordered == 50
    assert decision.fulfillable + decision.backordered == decision.requested


def test_unlisted_product_becomes_demand_not_a_refusal(depot, retail, product):
    """The retailer wants something the depot has never stocked."""
    decision = marketplace.decide_line(depot=depot, buyer=retail, product=product, quantity=200)
    assert decision.fulfillable == 0
    assert decision.backordered == 200
    assert decision.availability.reason == "not offered by this depot"
    assert demand_engine.origin_for(decision.availability) == BackorderLine.Origin.UNLISTED


def test_demand_board_aggregates_across_buyers(depot, product):
    a = Organization.objects.create(name="A", type="RETAIL")
    b = Organization.objects.create(name="B", type="RETAIL")
    demand_engine.capture(depot=depot, retail=a, product=product, quantity=100)
    demand_engine.capture(depot=depot, retail=b, product=product, quantity=250)

    board = demand_engine.demand_board(depot=depot)
    assert len(board) == 1
    assert board[0].quantity == 350
    assert board[0].buyers == 2
    assert board[0].lines == 2


def test_demand_becomes_a_purchase_requisition(depot, product):
    """The bridge: retail demand turns into something procurement can import."""
    a = Organization.objects.create(name="A", type="RETAIL")
    b = Organization.objects.create(name="B", type="RETAIL")
    demand_engine.capture(depot=depot, retail=a, product=product, quantity=100)
    demand_engine.capture(depot=depot, retail=b, product=product, quantity=250)

    requisition = demand_engine.raise_requisition_from_demand(depot=depot, user=None)

    assert isinstance(requisition, PurchaseRequisition)
    assert requisition.organization_id == depot.pk
    line = requisition.lines.get()
    assert line.product_id == product.pk
    assert line.quantity == 350, "both buyers' demand consolidated onto one line"

    assert set(BackorderLine.objects.values_list("status", flat=True)) == {
        BackorderLine.Status.SOURCING
    }
    assert BackorderLine.objects.filter(requisition=requisition).count() == 2


def test_demand_is_never_sourced_twice(depot, product):
    a = Organization.objects.create(name="A", type="RETAIL")
    demand_engine.capture(depot=depot, retail=a, product=product, quantity=100)
    demand_engine.raise_requisition_from_demand(depot=depot, user=None)

    with pytest.raises(demand_engine.DemandError):
        demand_engine.raise_requisition_from_demand(depot=depot, user=None)


def test_arriving_stock_settles_the_oldest_demand_first(depot, product):
    a = Organization.objects.create(name="A", type="RETAIL")
    b = Organization.objects.create(name="B", type="RETAIL")
    first = demand_engine.capture(depot=depot, retail=a, product=product, quantity=100)
    second = demand_engine.capture(depot=depot, retail=b, product=product, quantity=100)

    demand_engine.settle_backorders_for(depot=depot, product=product, quantity=150)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == BackorderLine.Status.FULFILLED
    assert first.quantity_fulfilled == 100
    assert second.status == BackorderLine.Status.OPEN
    assert second.quantity_fulfilled == 50, "partial fulfilment leaves the rest open"


# ---------------------------------------------------------------------------
# D5 — tender contracts
# ---------------------------------------------------------------------------


def test_tender_price_beats_the_list_price(depot, retail, product):
    stock(depot, product, 100)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("2500")
    )
    TenderContract.objects.create(
        tender_number="TND-1",
        depot=depot,
        client_org=retail,
        product=product,
        contract_price=Decimal("1800"),
        total_committed_qty=1000,
        valid_until=TODAY + timedelta(days=90),
    )

    assert marketplace.price_for(depot=depot, product=product, buyer=retail) == Decimal("1800")
    other = Organization.objects.create(name="Other", type="RETAIL")
    assert marketplace.price_for(depot=depot, product=product, buyer=other) == Decimal("2500")


def test_expired_or_exhausted_tender_does_not_govern(depot, retail, product):
    marketplace.publish(
        depot=depot, product=product, offered_qty=10, price_per_unit=Decimal("2500")
    )
    TenderContract.objects.create(
        tender_number="TND-OLD",
        depot=depot,
        client_org=retail,
        product=product,
        contract_price=Decimal("1800"),
        total_committed_qty=1000,
        valid_until=TODAY - timedelta(days=1),
    )
    assert marketplace.active_contract(depot=depot, product=product, buyer=retail) is None

    TenderContract.objects.create(
        tender_number="TND-FULL",
        depot=depot,
        client_org=retail,
        product=product,
        contract_price=Decimal("1800"),
        total_committed_qty=100,
        drawn_qty=100,
        valid_until=TODAY + timedelta(days=90),
    )
    assert marketplace.active_contract(depot=depot, product=product, buyer=retail) is None


# ---------------------------------------------------------------------------
# D6 — returns restock and credit
# ---------------------------------------------------------------------------


def test_approved_return_restocks_and_credits_only_accepted_units(depot, retail, product):
    request = CustomerReturn.objects.create(
        return_number="RET-1", depot=depot, retail=retail, reason="Over-ordered"
    )
    line = CustomerReturnLine.objects.create(
        return_request=request,
        product=product,
        batch_number="B1",
        expiry_date=TODAY + timedelta(days=200),
        quantity_returned=100,
        unit_price=Decimal("2500"),
    )

    returns.start_inspection(return_request=request)
    returns.record_inspection(line=line, quantity_accepted=80, quantity_rejected=20)
    outcome = returns.approve_return(return_request=request)

    assert outcome.restocked_units == 80
    assert outcome.rejected_units == 20
    assert outcome.credit_amount == Decimal("200000.00"), "only the 80 accepted are credited"

    batch = InventoryBatch.objects.get(organization=depot, product=product, batch_number="B1")
    assert batch.quantity_available == 80, "rejected units never re-enter saleable stock"
    assert outcome.credit_note is not None


def test_inspection_must_account_for_every_unit(depot, retail, product):
    request = CustomerReturn.objects.create(return_number="RET-2", depot=depot, retail=retail)
    line = CustomerReturnLine.objects.create(
        return_request=request,
        product=product,
        quantity_returned=100,
        unit_price=Decimal("2500"),
    )
    with pytest.raises(returns.ReturnError, match="accounted for"):
        returns.record_inspection(line=line, quantity_accepted=50, quantity_rejected=10)


def test_expired_goods_cannot_be_restocked(depot, retail, product):
    request = CustomerReturn.objects.create(return_number="RET-3", depot=depot, retail=retail)
    line = CustomerReturnLine.objects.create(
        return_request=request,
        product=product,
        batch_number="OLD",
        expiry_date=TODAY - timedelta(days=1),
        quantity_returned=10,
        unit_price=Decimal("2500"),
    )
    returns.start_inspection(return_request=request)
    returns.record_inspection(line=line, quantity_accepted=10, quantity_rejected=0)

    with pytest.raises(returns.ReturnError, match="expired"):
        returns.approve_return(return_request=request)


def test_approving_twice_does_not_duplicate_stock(depot, retail, product):
    request = CustomerReturn.objects.create(return_number="RET-4", depot=depot, retail=retail)
    line = CustomerReturnLine.objects.create(
        return_request=request,
        product=product,
        batch_number="B1",
        expiry_date=TODAY + timedelta(days=200),
        quantity_returned=50,
        unit_price=Decimal("1000"),
    )
    returns.start_inspection(return_request=request)
    returns.record_inspection(line=line, quantity_accepted=50, quantity_rejected=0)
    returns.approve_return(return_request=request)

    with pytest.raises(returns.ReturnError, match="already been approved"):
        returns.approve_return(return_request=request)

    batch = InventoryBatch.objects.get(organization=depot, product=product, batch_number="B1")
    assert batch.quantity_available == 50


# ---------------------------------------------------------------------------
# D7 — van stock
# ---------------------------------------------------------------------------


@pytest.fixture
def rep(depot):
    user = User.objects.create_user(username="rep-van", password="pw")
    return SalesRepresentative.objects.create(
        organization=depot,
        user=user,
        territory_code="KIGALI-N",
        monthly_sales_target=Decimal("1000000"),
        commission_rate_pct=Decimal("5.00"),
    )


def test_loading_a_van_takes_the_stock_out_of_the_depot(depot, rep, product):
    batch = stock(depot, product, 100)
    fieldsales.load_van(rep=rep, product=product, batch_number="B1", quantity=40)

    batch.refresh_from_db()
    assert batch.quantity_available == 60, "the depot no longer holds what is on the van"
    manifest = fieldsales.van_manifest(rep=rep)
    assert manifest["units_on_van"] == 40
    assert manifest["reconciles"] is True


def test_van_cannot_sell_what_it_does_not_hold(depot, rep, product):
    stock(depot, product, 100)
    fieldsales.load_van(rep=rep, product=product, batch_number="B1", quantity=10)
    with pytest.raises(fieldsales.VanError, match="cannot sell"):
        fieldsales.sell_from_van(rep=rep, product=product, batch_number="B1", quantity=11)


def test_van_round_trip_reconciles(depot, rep, product):
    batch = stock(depot, product, 100)
    fieldsales.load_van(rep=rep, product=product, batch_number="B1", quantity=50)
    fieldsales.sell_from_van(rep=rep, product=product, batch_number="B1", quantity=30)
    fieldsales.return_to_depot(rep=rep, product=product, batch_number="B1", quantity=20)

    manifest = fieldsales.van_manifest(rep=rep)
    assert manifest["units_on_van"] == 0
    assert manifest["units_sold"] == 30
    assert manifest["units_returned"] == 20
    assert manifest["reconciles"] is True

    batch.refresh_from_db()
    assert batch.quantity_available == 70, "50 left, 20 came back"


def test_expired_stock_cannot_be_loaded(depot, rep, product):
    stock(depot, product, 100, expiry_days=-1, batch="OLD")
    with pytest.raises(fieldsales.VanError, match="unexpired"):
        fieldsales.load_van(rep=rep, product=product, batch_number="OLD", quantity=10)


def test_rep_performance_uses_real_orders(depot, retail, rep, product):
    order = StockOrder.objects.create(
        depot=depot, retail=retail, order_number="PO-R1", ordered_by=rep.user
    )
    order.items.create(product=product, quantity_ordered=10, price_per_unit=Decimal("2500"))

    perf = fieldsales.performance(
        rep=rep, start=TODAY - timedelta(days=1), end=TODAY + timedelta(days=1)
    )
    assert perf.orders == 1
    assert perf.revenue == Decimal("25000.00")
    assert perf.commission == Decimal("1250.00"), "5% of 25,000"
    assert perf.target == Decimal("1000000.00")


def test_cancelled_orders_earn_no_commission(depot, retail, rep, product):
    order = StockOrder.objects.create(
        depot=depot,
        retail=retail,
        order_number="PO-R2",
        ordered_by=rep.user,
        status=StockOrder.Status.CANCELLED,
    )
    order.items.create(product=product, quantity_ordered=10, price_per_unit=Decimal("2500"))

    perf = fieldsales.performance(
        rep=rep, start=TODAY - timedelta(days=1), end=TODAY + timedelta(days=1)
    )
    assert perf.orders == 0
    assert perf.commission == Decimal("0.00")


# ---------------------------------------------------------------------------
# The two ways of offering, and which one wins
# ---------------------------------------------------------------------------


def test_inventory_offer_still_works_when_no_listing_is_published(depot, retail, product):
    """A depot that never adopted listings keeps trading — capped by real stock."""
    from apps.inventory.models import PharmacyProduct

    stock(depot, product, 40)
    PharmacyProduct.objects.create(
        organization=depot, product=product, wholesale_price=Decimal("900"), is_active=True
    )

    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.is_listed is True
    assert avail.price == Decimal("900")
    assert avail.available == 40, "the implicit offer never checked stock; now it does"


def test_a_published_listing_supersedes_the_inventory_offer(depot, retail, product):
    """Once a depot publishes a storefront listing, that listing is the offer."""
    from apps.inventory.models import PharmacyProduct

    stock(depot, product, 100)
    PharmacyProduct.objects.create(
        organization=depot, product=product, wholesale_price=Decimal("900"), is_active=True
    )
    marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=25,
        price_per_unit=Decimal("2500"),
        is_published=False,
    )

    avail = marketplace.availability(depot=depot, product=product, buyer=retail)
    assert avail.is_listed is False, "withdrawing the listing withdraws the product"
    assert avail.available == 0


# ---------------------------------------------------------------------------
# API robustness — found by the live walkthrough, not by the tests above
# ---------------------------------------------------------------------------


def test_stringified_null_buyer_does_not_crash_the_storefront(depot, product):
    """A frontend that interpolates a null must get an answer, not a 500.

    ``?buyer=None`` reached the ORM as a literal string and raised ValueError.
    A missing buyer is a legitimate question — "what is on offer generally" — so
    it reads as absent; only genuine garbage is refused.
    """
    from apps.iam.models import Role
    from rest_framework.test import APIClient

    buyer_org = Organization.objects.create(name="Buyer", type="RETAIL")
    user = User.objects.create_user(username="wt", password="x", organization=buyer_org)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    client = APIClient()
    client.force_authenticate(user=user)

    stock(depot, product, 10)
    marketplace.publish(depot=depot, product=product, offered_qty=10, price_per_unit=Decimal("100"))
    base = f"/api/distribution/storefront/availability/?depot={depot.pk}&product={product.pk}"

    for absent in ("None", "null", "undefined", ""):
        assert client.get(f"{base}&buyer={absent}").status_code == 200, absent
    for garbage in ("abc", "1.5"):
        assert client.get(f"{base}&buyer={garbage}").status_code == 400, garbage


def test_sourcing_twice_does_not_collide_on_a_blank_number(depot, product):
    """``requisition_number`` is unique — a blank default collides on the second raise.

    The first sourcing run silently produced a requisition with no number at all;
    the second failed with an IntegrityError. Found by the live walkthrough, which
    is the only thing that ran the operation twice against one database.
    """
    other = Product.objects.create(generic_name="Ibuprofen", strength="200mg")
    a = Organization.objects.create(name="A", type="RETAIL")
    demand_engine.capture(depot=depot, retail=a, product=product, quantity=100)
    first = demand_engine.raise_requisition_from_demand(depot=depot, user=None)

    demand_engine.capture(depot=depot, retail=a, product=other, quantity=50)
    second = demand_engine.raise_requisition_from_demand(depot=depot, user=None)

    assert first.requisition_number, "a requisition must carry a number"
    assert second.requisition_number
    assert first.requisition_number != second.requisition_number


# ---------------------------------------------------------------------------
# Endpoints the screens depend on — a 404 here is a blank screen in production
# ---------------------------------------------------------------------------


def _staff_client(org):
    from apps.iam.models import Role
    from rest_framework.test import APIClient

    user = User.objects.create_user(username="navcheck", password="x", organization=org)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_every_endpoint_the_distribution_screens_call_resolves(depot):
    """The GRN screen spent its whole life pointed at /grn/ — the route is /grns/.

    Nothing failed loudly: the screen just showed nothing. These are the exact
    paths the navigation's twelve entries load.
    """
    client = _staff_client(depot)
    for path in [
        "/api/distribution/orders/",
        "/api/distribution/in-transit/",
        "/api/distribution/grns/",
        "/api/distribution/listings/",
        "/api/distribution/tenders/",
        "/api/distribution/returns/",
        "/api/distribution/backorders/",
        "/api/distribution/sales-reps/",
        "/api/distribution/van-stock/",
        "/api/distribution/van-movements/",
        "/api/catalog/suppliers/",
        f"/api/distribution/overview/?depot={depot.pk}",
        f"/api/distribution/storefront/?depot={depot.pk}",
        f"/api/distribution/demand/?depot={depot.pk}",
        f"/api/distribution/rep-performance/?organization={depot.pk}",
    ]:
        assert client.get(path).status_code == 200, path


def test_order_status_filter_is_honoured_not_ignored(depot, retail, product):
    """An ignored filter is worse than a rejected one — the count looks plausible.

    The overview asked for ``?status=PENDING`` and was handed every order.
    """
    client = _staff_client(depot)
    StockOrder.objects.create(
        depot=depot, retail=retail, order_number="PO-P1", status=StockOrder.Status.PENDING
    )
    StockOrder.objects.create(
        depot=depot, retail=retail, order_number="PO-D1", status=StockOrder.Status.DELIVERED
    )

    assert client.get("/api/distribution/orders/").json()["count"] == 2
    assert client.get("/api/distribution/orders/?status=PENDING").json()["count"] == 1
    assert client.get("/api/distribution/orders/?status=DELIVERED").json()["count"] == 1
    # A typo must be refused, not quietly treated as "no filter".
    assert client.get("/api/distribution/orders/?status=PENDNIG").status_code == 400


def test_demand_summary_separates_actionable_from_already_sourced(depot, product):
    """The headline must match what the button does.

    Sourcing only picks up OPEN demand. A summary that adds SOURCING into the same
    total shows a manager 1,745 units and then raises a requisition for 35.
    """
    a = Organization.objects.create(name="A", type="RETAIL")
    b = Organization.objects.create(name="B", type="RETAIL")
    demand_engine.capture(depot=depot, retail=a, product=product, quantity=1000)
    demand_engine.raise_requisition_from_demand(depot=depot, user=None)
    demand_engine.capture(depot=depot, retail=b, product=product, quantity=35)

    s = demand_engine.summary(depot=depot)
    assert s["units_open"] == 35, "only the un-sourced demand is actionable"
    assert s["units_sourcing"] == 1000
    assert s["units_wanted"] == 1035, "everything still outstanding"

    requisition = demand_engine.raise_requisition_from_demand(depot=depot, user=None)
    assert (
        requisition.lines.get().quantity == s["units_open"]
    ), "the requisition must cover exactly what the headline promised"


def test_declining_backorder_still_ships_what_is_available(depot, retail, product):
    """ "No backorders" means do not record demand — not refuse a partial supply."""
    stock(depot, product, 5)
    marketplace.publish(
        depot=depot, product=product, offered_qty=100, price_per_unit=Decimal("1500")
    )
    decision = marketplace.decide_line(
        depot=depot, buyer=retail, product=product, quantity=40, allow_backorder=False
    )
    assert decision.fulfillable == 5
    assert decision.backordered == 0, "the shortfall is dropped, not recorded"


def test_models_render_as_text_without_crashing(depot, retail, product, rep):
    """``__str__`` is called by the admin, by error messages and by DRF.

    Two of these interpolated ``product.name``, which does not exist on ``Product``
    — so merely rendering the object raised AttributeError. Nothing exercised them,
    so nothing caught it.
    """
    listing = marketplace.publish(
        depot=depot, product=product, offered_qty=10, price_per_unit=Decimal("100")
    )
    stock(depot, product, 50)
    fieldsales.load_van(rep=rep, product=product, batch_number="B1", quantity=5)
    van = VanStock.objects.get(rep=rep, product=product, batch_number="B1")

    for obj in [
        listing,
        van,
        BackorderLine(depot=depot, retail=retail, product=product, quantity=1),
    ]:
        assert str(obj)


def test_approving_a_return_reports_the_credit_note_number(depot, retail, product):
    """The API read ``document_number``; the field is ``doc_number``.

    Approval would have raised AttributeError at the point of responding — after
    the goods had already been restocked and the credit note issued.
    """
    client = _staff_client(depot)
    request = CustomerReturn.objects.create(return_number="RET-API-1", depot=depot, retail=retail)
    line = CustomerReturnLine.objects.create(
        return_request=request,
        product=product,
        batch_number="B1",
        expiry_date=TODAY + timedelta(days=200),
        quantity_returned=10,
        unit_price=Decimal("500"),
    )
    resp = client.post(
        f"/api/distribution/returns/{request.pk}/inspect/",
        {"lines": [{"id": line.pk, "quantity_accepted": 10, "quantity_rejected": 0}]},
        format="json",
    )
    assert resp.status_code == 200, resp.content

    resp = client.post(f"/api/distribution/returns/{request.pk}/approve/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["restocked_units"] == 10
    assert body["credit_amount"] == "5000.00"
    assert body["credit_note_number"], "the issued credit note must be named in the response"
