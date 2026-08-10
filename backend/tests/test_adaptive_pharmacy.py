"""A pharmacy that is one or two people.

Most Rwandan community pharmacies are not departmental. The Rwanda Community
Pharmacists Union represents a few hundred pharmacists and technicians across
the whole country, and the ordinary shop is an owner plus perhaps one employee
who between them do the selling, the ordering, the receiving, the cash and the
books.

The system was built for the other shape, and three things followed from that
which this file pins down:

* **A one-person pharmacy could not approve anything.** "No self-approval" is
  the right rule when there is somebody else to ask. When there is not, it does
  not produce a second approver — it produces a pharmacy that cannot run its
  own payroll, so the work moves outside the system and no record exists at
  all. Allowed now, with a written reason, and flagged.

* **Nothing said the control was absent.** The same person creating an order,
  receiving it and approving its payment is normal at this size and unavoidable.
  Pretending otherwise is how a system implies a separation it does not have.

* **The till gave medicine away.** A product nothing prices resolved to zero and
  the sale completed: stock off the shelf, no money, and the only trace a
  negative gross profit at month end. In a two-person shop nobody else notices.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import ApprovalError, claim, decide, request_approval
from apps.catalog.models import Product
from apps.core.pharmacy_day import control_notice, pharmacy_day
from apps.iam.models import Organization, Permission, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail.models import Sale, SaleItem
from apps.retail.services import complete_sale

pytestmark = pytest.mark.django_db


def _role(code: str, *permission_codes: str) -> Role:
    role, _ = Role.objects.get_or_create(code=code, defaults={"name": code})
    for code_ in permission_codes:
        permission, _ = Permission.objects.get_or_create(
            code=code_, defaults={"description": code_}
        )
        role.permissions.add(permission)
    return role


@pytest.fixture
def shop() -> Organization:
    """A two-person community pharmacy — the ordinary case."""
    return Organization.objects.create(
        name="Kigali Care Pharmacy",
        type="RETAIL",
        tin="400500600",
        size=Organization.Size.MICRO,
    )


@pytest.fixture
def chain() -> Organization:
    return Organization.objects.create(
        name="Regional Group", type="RETAIL", tin="7", size=Organization.Size.MEDIUM
    )


@pytest.fixture
def owner(shop: Organization) -> User:
    user = User.objects.create_user(username="jean", password="x", organization=shop)
    user.roles.add(
        _role(
            "PHARMACY_OWNER",
            "order.create",
            "order.approve",
            "order.receive",
            "finance.manage",
            # An unregistered resource type falls back to demanding
            # `organization.manage`; these tests are about self-approval, not
            # about competence, so the owner holds it rather than the tests
            # asserting the wrong refusal.
            "organization.manage",
        )
    )
    return user


# --------------------------------------------------------------------------- #


class TestApprovalWhenThereIsNobodyElse:
    @staticmethod
    def _request(org: Organization, user: User) -> ApprovalRequest:
        # A resource type of this file's own. `registry` is module-level and
        # persists across tests, so registering a handler for a name another
        # file relies on being *un*registered breaks that file — which is
        # exactly what "test.thing" did to test_approvals.py, and only in the
        # full run, never when this file was run alone.
        registry.register("test.adaptive")(lambda approval: None)
        return request_approval(
            resource_type="test.adaptive",
            resource_id="1",
            organization=org,
            requested_by=user,
            reason="Monthly restock",
        )

    def test_a_single_handed_pharmacy_can_approve_its_own_request(
        self, shop: Organization, owner: User
    ) -> None:
        """Otherwise nothing it raises can ever be decided."""
        approval = self._request(shop, owner)
        claim(approval=approval, user=owner)
        decided = decide(
            approval=approval,
            user=owner,
            approve=True,
            note="I am the only person here; stock was down to two boxes.",
        )
        assert decided.status == ApprovalRequest.Status.APPROVED

    def test_and_the_decision_is_marked_as_self_approved(
        self, shop: Organization, owner: User
    ) -> None:
        """An auditor cannot otherwise tell it from a decision two people made."""
        approval = self._request(shop, owner)
        claim(approval=approval, user=owner)
        decided = decide(approval=approval, user=owner, approve=True, note="Only me here.")
        assert decided.self_approved is True

    def test_it_must_say_why(self, shop: Organization, owner: User) -> None:
        """The note is the whole of the control that survives."""
        approval = self._request(shop, owner)
        claim(approval=approval, user=owner)
        with pytest.raises(ApprovalError, match="Say why"):
            decide(approval=approval, user=owner, approve=True, note="   ")

    def test_a_larger_pharmacy_still_cannot(self, chain: Organization) -> None:
        """Where a second person exists, the rule is unchanged."""
        manager = User.objects.create_user(username="mgr", password="x", organization=chain)
        manager.roles.add(_role("BRANCH_MANAGER", "order.approve", "organization.manage"))
        approval = self._request(chain, manager)
        with pytest.raises(ApprovalError, match="no self-approval"):
            claim(approval=approval, user=manager)

    def test_a_decision_by_somebody_else_is_not_flagged(self, chain: Organization) -> None:
        clerk = User.objects.create_user(username="clerk", password="x", organization=chain)
        approver = User.objects.create_user(username="boss", password="x", organization=chain)
        approver.roles.add(_role("BRANCH_MANAGER", "order.approve", "organization.manage"))
        approval = self._request(chain, clerk)
        claim(approval=approval, user=approver)
        decided = decide(approval=approval, user=approver, approve=True, note="fine")
        assert decided.self_approved is False


class TestTheControlNoticeIsHonest:
    def test_it_names_the_person_who_can_do_the_whole_cycle(
        self, shop: Organization, owner: User
    ) -> None:
        notice = control_notice(shop)
        assert notice is not None
        assert "jean" in notice["body"].lower() or "Jean" in notice["body"]
        assert "purchase order" in notice["body"]
        assert notice["what_helps"], "a notice that only worries is not useful"

    def test_it_does_not_pretend_the_arrangement_is_forbidden(
        self, shop: Organization, owner: User
    ) -> None:
        """Refusing a one-person pharmacy the right to buy stock is an outage,
        not a control."""
        notice = control_notice(shop)
        assert notice is not None
        assert "recorded rather than prevented" in notice["body"]

    def test_a_staffed_pharmacy_gets_no_notice(self, chain: Organization) -> None:
        for name in ("a", "b", "c"):
            User.objects.create_user(username=name, password="x", organization=chain)
        assert control_notice(chain) is None


class TestTheTillWillNotGiveMedicineAway:
    @staticmethod
    def _open_sale(org: Organization, price: Decimal) -> Sale:
        product = Product.objects.create(generic_name="Paracetamol", strength="500mg")
        PharmacyProduct.objects.create(organization=org, product=product, is_active=True)
        InventoryBatch.objects.create(
            organization=org,
            product=product,
            batch_number="B1",
            expiry_date=date.today() + timedelta(days=365),
            quantity_available=100,
            wholesale_cost=Decimal("300"),
            status=InventoryBatch.Status.ACTIVE,
        )
        sale = Sale.objects.create(organization=org, status=Sale.Status.OPEN)
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=Decimal("1"),
            quantity_base=Decimal("1"),
            unit_price=price,
        )
        return sale

    def test_a_line_with_no_price_is_refused(self, shop: Organization, owner: User) -> None:
        """SALE-000018 took RWF 0 for a paracetamol that cost RWF 300."""
        sale = self._open_sale(shop, Decimal("0"))
        with pytest.raises(ValueError, match="give the medicine away"):
            complete_sale(sale=sale, payments=[{"amount": Decimal("0")}], user=owner)
        sale.refresh_from_db()
        assert sale.status == Sale.Status.OPEN, "the stock must not have left the shelf"

    def test_the_refusal_names_the_medicine(self, shop: Organization, owner: User) -> None:
        """ "A line has no price" sends somebody hunting through the basket."""
        sale = self._open_sale(shop, Decimal("0"))
        with pytest.raises(ValueError, match="Paracetamol"):
            complete_sale(sale=sale, payments=[{"amount": Decimal("0")}], user=owner)

    def test_a_priced_sale_still_completes(self, shop: Organization, owner: User) -> None:
        sale = self._open_sale(shop, Decimal("500"))
        completed = complete_sale(
            sale=sale, payments=[{"amount": Decimal("500"), "method": "CASH"}], user=owner
        )
        assert completed.status == Sale.Status.COMPLETED


class TestTheDayIsHonestAboutProfit:
    def test_takings_are_not_reported_as_profit(self, shop: Organization, owner: User) -> None:
        """Revenue, cost and gross profit are separate numbers, always."""
        day = pharmacy_day(owner)
        assert set(day["today"]) >= {"revenue", "cost_of_goods", "gross_profit"}
        assert day["today"]["revenue"] != day["today"]["gross_profit"] or (
            day["today"]["revenue"]["amount"] == "0.00"
        )

    def test_it_says_when_expenses_have_not_been_recorded(
        self, shop: Organization, owner: User
    ) -> None:
        """Otherwise gross profit is presented as what the owner keeps."""
        day = pharmacy_day(owner)
        assert day["month"]["expenses_recorded"] is False

    def test_it_reports_how_much_of_the_margin_it_is_sure_about(
        self, shop: Organization, owner: User
    ) -> None:
        """A pharmacy that has not entered costs otherwise reads 100% margin as
        good news."""
        assert "lines_without_cost" in day_today(owner)

    def test_the_size_travels_with_the_answer(self, shop: Organization, owner: User) -> None:
        """The screen has to know which pharmacy it is drawing."""
        assert pharmacy_day(owner)["organization"]["size"] == Organization.Size.MICRO


def day_today(user: User) -> dict:
    return pharmacy_day(user)["today"]
