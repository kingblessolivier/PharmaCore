from datetime import date
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.distribution.models import (
    CustomerReturn,
    DepotProductListing,
    JourneyPlan,
    SalesRepresentative,
    SalesVisitLog,
    TenderContract,
)
from apps.iam.models import Organization, User

pytestmark = pytest.mark.django_db


def test_depot_offered_listing_decoupled_from_physical_stock():
    depot = Organization.objects.create(name="Kigali Central Depot", type="DEPOT")
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")

    listing = DepotProductListing.objects.create(
        depot=depot,
        product=product,
        offered_qty=100,
        buffer_qty=20,
        price_per_unit=Decimal("2500.00"),
        is_published=True,
    )
    assert listing.available_for_order == 80
    assert listing.is_published is True


def test_sales_rep_and_journey_plan():
    depot = Organization.objects.create(name="Kigali Central Depot", type="DEPOT")
    retail = Organization.objects.create(name="Gasabo Pharmacy", type="RETAIL")
    user = User.objects.create_user(username="rep1", password="password")

    rep = SalesRepresentative.objects.create(
        organization=depot,
        user=user,
        territory_code="KIGALI-NORTH",
        monthly_sales_target=Decimal("5000000.00"),
    )

    plan = JourneyPlan.objects.create(
        rep=rep,
        customer_org=retail,
        planned_date=date(2026, 8, 10),
    )

    visit = SalesVisitLog.objects.create(
        journey_plan=plan,
        rep=rep,
        customer_org=retail,
        visit_type=SalesVisitLog.VisitType.PRE_SALE,
        notes="Customer requested 50 boxes Amoxicillin",
        sales_amount=Decimal("125000.00"),
    )
    assert visit.sales_amount == Decimal("125000.00")
    assert visit.customer_org == retail


def test_tender_contract_price_and_remaining_quantity():
    depot = Organization.objects.create(name="Kigali Central Depot", type="DEPOT")
    hospital = Organization.objects.create(name="King Faisal Hospital", type="RETAIL")
    product = Product.objects.create(generic_name="Paracetamol IV", strength="10mg/ml")

    contract = TenderContract.objects.create(
        tender_number="TND-2026-0099",
        depot=depot,
        client_org=hospital,
        product=product,
        contract_price=Decimal("1800.00"),
        total_committed_qty=1000,
        drawn_qty=250,
        valid_until=date(2026, 12, 31),
    )
    assert contract.remaining_qty == 750


def test_customer_return_workflow():
    depot = Organization.objects.create(name="Kigali Central Depot", type="DEPOT")
    retail = Organization.objects.create(name="Nyarugenge Pharmacy", type="RETAIL")

    ret = CustomerReturn.objects.create(
        return_number="RET-2026-0012",
        depot=depot,
        retail=retail,
        reason="Near-expiry batch returned for credit",
        credit_note_amount=Decimal("45000.00"),
    )
    assert ret.status == CustomerReturn.Status.REQUESTED
    ret.status = CustomerReturn.Status.APPROVED
    ret.save()
    assert ret.status == CustomerReturn.Status.APPROVED
