"""VAT, money and performance for a small pharmacy.

Three things this pins.

**VAT was charged by every pharmacy in the system.** Each sale line took its
rate from the product's tax class and nothing else, so an unregistered shop
added 18% to a paracetamol. The RRA makes registration compulsory only above
RWF 20,000,000 of turnover in twelve months; below it a pharmacy must not charge
VAT at all. Most Rwandan community pharmacies are below it, so for most of them
the till was wrong on every line it rang.

**Money owed is not money.** A day that rings RWF 400,000 of which RWF 250,000
is an insurance claim has not put RWF 400,000 anywhere. The Money screen has to
keep those apart or it teaches an owner to plan around money they have not got.

**A score with no method is a rating.** The operational health figure is only
defensible if every component is shown with the rule behind it, and if a
component with no evidence is dropped rather than scored zero — a pharmacy that
opened last week is not failing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.core.money_centre import money_centre, turnover_12m
from apps.core.pharmacy_performance import pharmacy_performance
from apps.core.setup import SetupError, apply_setup, setup_state
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail import tax as vat
from apps.retail.models import Payment, Sale, SaleItem
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def shop() -> Organization:
    return Organization.objects.create(
        name="Kigali Care Pharmacy", type="RETAIL", tin="400500600", size=Organization.Size.MICRO
    )


@pytest.fixture
def owner(shop: Organization) -> User:
    return User.objects.create_user(username="jean", password="x", organization=shop)


@pytest.fixture
def paracetamol() -> Product:
    # Class B is standard-rated: 18% *if the pharmacy is registered*.
    return Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")


# --------------------------------------------------------------------------- #


class TestVatFollowsRegistrationNotTheProduct:
    def test_an_unregistered_pharmacy_charges_nothing(
        self, shop: Organization, paracetamol: Product
    ) -> None:
        assert shop.is_vat_registered is False, "a pharmacy is not registered until it says so"
        assert vat.rate_for(product=paracetamol, organization=shop) == Decimal("0")

    def test_a_registered_one_charges_the_product_rate(
        self, shop: Organization, paracetamol: Product
    ) -> None:
        shop.is_vat_registered = True
        shop.save(update_fields=["is_vat_registered"])
        assert vat.rate_for(product=paracetamol, organization=shop) == Decimal("18.00")

    def test_the_tax_class_is_not_overwritten(
        self, shop: Organization, paracetamol: Product
    ) -> None:
        """The medicine's own rating stays true, so registering later just works."""
        vat.rate_for(product=paracetamol, organization=shop)
        paracetamol.refresh_from_db()
        assert paracetamol.tax_class == "B"

    def test_an_exempt_medicine_is_still_exempt_when_registered(self, shop: Organization) -> None:
        shop.is_vat_registered = True
        shop.save(update_fields=["is_vat_registered"])
        exempt = Product.objects.create(generic_name="Insulin", tax_class="A")
        assert vat.rate_for(product=exempt, organization=shop) == Decimal("0")

    def test_crossing_the_threshold_is_reported_not_enforced(self, shop: Organization) -> None:
        """Registering happens at the RRA. The system's job is to say when."""
        assert vat.registration_check(shop, turnover_12m=Decimal("4000000")) is None

        notice = vat.registration_check(shop, turnover_12m=Decimal("24000000"))
        assert notice is not None
        assert "compulsory" in notice["body"]
        # Still not charging, because there is no registration number to put on
        # an invoice.
        assert shop.is_vat_registered is False

    def test_a_registered_pharmacy_is_not_nagged(self, shop: Organization) -> None:
        shop.is_vat_registered = True
        shop.save(update_fields=["is_vat_registered"])
        assert vat.registration_check(shop, turnover_12m=Decimal("99000000")) is None


class TestMoneyOwedIsNotMoney:
    def _sale(self, shop: Organization, *, cash: Decimal, insured: Decimal) -> Sale:
        product = Product.objects.create(generic_name="Amoxicillin")
        sale = Sale.objects.create(
            organization=shop,
            status=Sale.Status.COMPLETED,
            completed_at=timezone.now(),
            sale_number=f"S-{cash}-{insured}",
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=Decimal("1"),
            quantity_base=Decimal("1"),
            unit_price=cash + insured,
        )
        if cash > 0:
            Payment.objects.create(sale=sale, method=Payment.Method.CASH, amount=cash)
        if insured > 0:
            Payment.objects.create(sale=sale, method=Payment.Method.INSURANCE, amount=insured)
        return sale

    def test_insurance_is_kept_out_of_what_you_received(
        self, shop: Organization, owner: User
    ) -> None:
        self._sale(shop, cash=Decimal("150000"), insured=Decimal("250000"))
        took = money_centre(owner)["took_today"]

        assert took["actually_received"]["amount"] == "150000.00"
        assert took["on_insurance"]["amount"] == "250000.00"
        assert took["total_rung_up"]["amount"] == "400000.00", "the till did ring 400,000"

    def test_the_screen_says_so_in_words(self, shop: Organization, owner: User) -> None:
        """The distinction is worthless if only the developer knows about it."""
        assert "not money you have" in money_centre(owner)["as_at_note"]

    def test_turnover_is_measured_over_twelve_months(self, shop: Organization, owner: User) -> None:
        """It is the figure the VAT threshold is judged on."""
        self._sale(shop, cash=Decimal("30000"), insured=Decimal("0"))
        assert turnover_12m([shop.pk]) == Decimal("30000.00")


class TestTheScoreShowsItsWorking:
    def test_a_component_with_no_evidence_is_not_scored_zero(
        self, shop: Organization, owner: User
    ) -> None:
        """A pharmacy that opened last week is new, not failing."""
        health = pharmacy_performance(owner)["health"]
        trend = next(c for c in health["components"] if c["name"] == "Sales trend")
        assert trend["score"] is None
        assert trend["basis"], "a component without a rule is a number nobody can argue with"

    def test_every_component_carries_the_rule_behind_it(
        self, shop: Organization, owner: User
    ) -> None:
        for component in pharmacy_performance(owner)["health"]["components"]:
            assert component["basis"], f"{component['name']} has no stated basis"

    def test_it_says_what_it_is_not(self, shop: Organization, owner: User) -> None:
        caveat = pharmacy_performance(owner)["health"]["caveat"]
        assert "not a credit score" in caveat

    def test_the_comparison_period_is_like_for_like(self, shop: Organization, owner: User) -> None:
        """The 3rd of the month must not be judged against a whole month."""
        # The 3rd is three days into August, so it is compared against the
        # first three days of July — not against the whole of July.
        performance = pharmacy_performance(owner, on=date(2026, 8, 3))
        assert performance["period"]["compared_with"] == "2026-07-01 to 2026-07-03"


class TestSetupDecidesWhatIsOffered:
    def test_one_person_is_a_micro_pharmacy(self, shop: Organization) -> None:
        apply_setup(organization=shop, headcount="1", branches=1, manages=["finance"])
        shop.refresh_from_db()
        assert shop.size == Organization.Size.MICRO
        assert shop.feature_flags["finance"] is True
        assert shop.feature_flags["hr"] is False

    def test_several_branches_outgrow_the_short_menu(self, shop: Organization) -> None:
        """Branches have to be able to see each other, whatever the headcount."""
        apply_setup(organization=shop, headcount="1", branches=4)
        shop.refresh_from_db()
        assert shop.size == Organization.Size.MEDIUM

    def test_registering_for_vat_needs_the_number(self, shop: Organization) -> None:
        """It goes on every invoice, so it is needed before the till charges."""
        with pytest.raises(SetupError, match="registration number"):
            apply_setup(organization=shop, headcount="1", vat_registered=True)

    def test_registering_properly_turns_the_tax_on(self, shop: Organization) -> None:
        apply_setup(
            organization=shop,
            headcount="2-5",
            vat_registered=True,
            vat_registration_no="102938475",
        )
        shop.refresh_from_db()
        assert shop.is_vat_registered is True
        product = Product.objects.create(generic_name="Ibuprofen", tax_class="B")
        assert vat.rate_for(product=product, organization=shop) == Decimal("18.00")

    def test_a_nonsense_headcount_is_refused_by_name(self, shop: Organization) -> None:
        with pytest.raises(SetupError, match="how many people work here"):
            apply_setup(organization=shop, headcount="a few")

    def test_an_unanswered_pharmacy_is_distinguishable_from_one_that_chose_nothing(
        self, shop: Organization
    ) -> None:
        assert setup_state(shop)["answered"] is False
        apply_setup(organization=shop, headcount="1", manages=[])
        shop.refresh_from_db()
        assert setup_state(shop)["answered"] is True


class TestWhatIsOnTheShelf:
    def test_stock_is_valued_at_cost_not_at_the_shelf_price(
        self, shop: Organization, owner: User, paracetamol: Product
    ) -> None:
        """Valuing stock at what it will sell for books a profit nobody made."""
        PharmacyProduct.objects.create(
            organization=shop, product=paracetamol, is_active=True, retail_price=Decimal("500")
        )
        InventoryBatch.objects.create(
            organization=shop,
            product=paracetamol,
            batch_number="B1",
            expiry_date=date.today() + timedelta(days=365),
            quantity_available=10,
            wholesale_cost=Decimal("300"),
            status=InventoryBatch.Status.ACTIVE,
        )
        assert pharmacy_performance(owner)["stock_value"]["amount"] == "3000.00"


class TestReceivingWithoutAPurchaseOrder:
    """A rep's van stops outside and the pharmacist buys four boxes.

    Every other path into inventory runs through procurement, and the nearest
    one — `IntakeView` — refuses retail outright: "Only depots receive supplier
    intake." That is right for a branch supplied by its own depot and wrong for
    an independent community pharmacy, which is most of them here. Until this
    existed the delivery could not be recorded at all, so the shelf and the
    system parted company in the first week.
    """

    @staticmethod
    def _receive(shop: Organization, product: Product, **overrides: object) -> dict:
        from apps.inventory.quick_receive import quick_receive

        payload: dict = {
            "organization": shop,
            "product": product,
            "quantity": Decimal("20"),
            "batch_number": "AMX-2604",
            "expiry_date": date.today() + timedelta(days=600),
            "unit_cost": Decimal("2800"),
            "selling_price": Decimal("3500"),
            "supplier_name": "Rep van",
        }
        payload.update(overrides)
        return quick_receive(**payload)

    def test_the_stock_lands_and_the_medicine_is_listed(
        self, shop: Organization, paracetamol: Product
    ) -> None:
        result = self._receive(shop, paracetamol)

        assert result["received"] == "20", "a quantity a person can read, not 2E+1"
        assert result["on_hand_now"] == "20"
        assert result["margin_pct"] == 20.0
        assert PharmacyProduct.objects.filter(
            organization=shop, product=paracetamol, is_active=True
        ).exists(), "stock the till cannot find is not on sale"

    def test_expired_stock_is_turned_away(self, shop: Organization, paracetamol: Product) -> None:
        from apps.inventory.quick_receive import QuickReceiveError

        with pytest.raises(QuickReceiveError, match="send it back"):
            self._receive(shop, paracetamol, expiry_date=date.today() - timedelta(days=1))

    def test_a_batch_number_is_not_optional(self, shop: Organization, paracetamol: Product) -> None:
        """Traceability to the lot is what a recall runs on."""
        from apps.inventory.quick_receive import QuickReceiveError

        with pytest.raises(QuickReceiveError, match="recall"):
            self._receive(shop, paracetamol, batch_number="  ")

    def test_selling_below_cost_is_questioned(
        self, shop: Organization, paracetamol: Product
    ) -> None:
        from apps.inventory.quick_receive import QuickReceiveError

        with pytest.raises(QuickReceiveError, match="loses money"):
            self._receive(shop, paracetamol, selling_price=Decimal("1000"))

    def test_a_depot_is_sent_back_to_its_purchase_order(self, paracetamol: Product) -> None:
        """Not a way round the three-way match."""
        from apps.inventory.quick_receive import QuickReceiveError

        depot = Organization.objects.create(name="Central Depot", type="DEPOT", tin="9")
        with pytest.raises(QuickReceiveError, match="purchase order"):
            self._receive(depot, paracetamol)
