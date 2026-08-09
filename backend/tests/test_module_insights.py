"""A module home that reports figures instead of repeating the menu.

Every home page used to end in a grid of cards that linked into the app's own
navigation — the menu again, one click deeper. These pin the replacement: real
aggregates, scoped to what the viewer may see, shaped so the frontend can render
any module uniformly.

The two properties worth defending are that **nothing is invented** (an empty
module reports empty rather than drawing a plausible chart) and that **nothing
leaks** (a cashier does not learn the group's payables from a pie chart).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.models import Account, CustomerInvoice, JournalEntry, JournalLine
from apps.iam.models import Organization, Permission, Role, User
from apps.insurance.models import Claim, InsuranceScheme, MemberPolicy
from apps.inventory.models import InventoryBatch
from apps.retail.models import Payment, Sale, SaleItem
from apps.workspace import moduleinsights
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

SHAPE = {"tiles", "donuts", "bars", "trend", "trend_series"}


def today():
    return timezone.localdate()


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def person(org, name, *permissions):
    user = User.objects.create_user(username=name, password="pw", organization=org)
    if permissions:
        role = Role.objects.create(code=f"ROLE_{name.upper()}", name=name)
        for code in permissions:
            role.permissions.add(
                Permission.objects.get_or_create(code=code, defaults={"name": code})[0]
            )
        user.roles.add(role)
    return user


def product(name="Amoxicillin"):
    return Product.objects.create(generic_name=name, strength="500mg")


def batch(org, prod, *, qty=10, cost="1000", days=365, status=InventoryBatch.Status.ACTIVE):
    return InventoryBatch.objects.create(
        organization=org,
        product=prod,
        batch_number=f"B{qty}{days}",
        expiry_date=today() + timedelta(days=days),
        quantity_available=qty,
        wholesale_cost=Decimal(cost),
        status=status,
    )


def completed_sale(org, prod, *, method="CASH", when=None, price="2000"):
    sale = Sale.objects.create(
        organization=org,
        status=Sale.Status.COMPLETED,
        completed_at=when or timezone.now(),
        sale_number=f"S-{Sale.objects.count() + 1:04d}",
    )
    SaleItem.objects.create(sale=sale, product=prod, quantity=1, unit_price=Decimal(price))
    Payment.objects.create(sale=sale, method=method, amount=Decimal(price))
    return sale


# ---------------------------------------------------------------------------
# Shape — the frontend renders every module through one component
# ---------------------------------------------------------------------------


def test_every_module_returns_the_same_four_keys(org):
    """One payload shape is what lets nine homes share a single renderer."""
    boss = person(org, "boss", *{perm for perm, _ in moduleinsights._MODULES.values()})
    for module in moduleinsights._MODULES:
        payload = moduleinsights.insights_for(boss, module)
        assert set(payload) == SHAPE, module
        assert isinstance(payload["tiles"], list)


def test_an_unknown_module_is_empty_rather_than_an_error(org):
    """The nav and this registry can drift; a 500 on a home page cannot be right."""
    assert moduleinsights.insights_for(person(org, "someone"), "nonsense") == {
        "tiles": [],
        "donuts": [],
        "bars": [],
        "trend": [],
        "trend_series": [],
    }


def test_an_empty_module_reports_empty_rather_than_inventing_a_chart(org):
    """The failure that matters: a convincing pie drawn from no data."""
    viewer = person(org, "viewer", "insurance.view")
    payload = moduleinsights.insights_for(viewer, "insurance")
    assert all(d["slices"] == [] for d in payload["donuts"])
    assert all(b["data"] == [] for b in payload["bars"])
    assert [t["value"] for t in payload["tiles"]] == [0, 0.0]


# ---------------------------------------------------------------------------
# Permission — the same gate as the work queue
# ---------------------------------------------------------------------------


def test_a_module_you_cannot_see_returns_nothing(org):
    """A cashier must not learn the payables from a chart they were never shown."""
    CustomerInvoice.objects.create(
        organization=org,
        customer=org,
        invoice_number="INV-1",
        invoice_date=today(),
        due_date=today() - timedelta(days=90),
        total_amount=Decimal("500000"),
        amount_paid=Decimal("0"),
        status=CustomerInvoice.Status.OVERDUE,
    )
    cashier = person(org, "cashier", "sale.create")

    assert moduleinsights.insights_for(cashier, "finance")["tiles"] == []
    # ...and the module they *do* hold still answers.
    assert moduleinsights.insights_for(cashier, "retail")["tiles"] != []


def test_figures_stop_at_the_edge_of_what_you_can_see(org):
    """Two pharmacies, one system: a batch next door is not your stock."""
    other = Organization.objects.create(name="Nyabugogo Pharmacy", type="RETAIL")
    prod = product()
    batch(org, prod, qty=10, cost="1000")
    batch(other, prod, qty=999, cost="1000", days=200)

    viewer = person(org, "keeper", "inventory.view")
    tiles = {
        t["label"]: t["value"] for t in moduleinsights.insights_for(viewer, "inventory")["tiles"]
    }
    assert tiles["Batches on hand"] == 1
    assert tiles["Stock at cost"] == 10_000.0


# ---------------------------------------------------------------------------
# The figures themselves
# ---------------------------------------------------------------------------


def test_stock_value_is_banded_by_how_long_it_has_left(org):
    """Banded because the action differs: sell through, move it, or write it off."""
    prod = product()
    batch(org, prod, qty=1, cost="100", days=-5)
    batch(org, prod, qty=2, cost="100", days=10)
    batch(org, prod, qty=3, cost="100", days=60)
    batch(org, prod, qty=4, cost="100", days=400)

    viewer = person(org, "keeper", "inventory.view")
    donut = moduleinsights.insights_for(viewer, "inventory")["donuts"][0]
    assert {s["label"]: s["value"] for s in donut["slices"]} == {
        "Expired": 100.0,
        "Within 30 days": 200.0,
        "31-90 days": 300.0,
        "Over 90 days": 400.0,
    }


def test_the_tender_mix_counts_every_payment(org):
    """The mix decides whether the drawer balances and what the fees cost."""
    prod = product()
    completed_sale(org, prod, method="CASH")
    completed_sale(org, prod, method="CASH")
    completed_sale(org, prod, method="MOBILE_MONEY")

    cashier = person(org, "till", "sale.create")
    donut = moduleinsights.insights_for(cashier, "retail")["donuts"][0]
    assert {s["label"]: s["value"] for s in donut["slices"]} == {"Cash": 2, "Mobile Money": 1}


def test_the_revenue_trend_is_fourteen_days_including_the_quiet_ones(org):
    """A gap drawn as a missing point reads as a broken chart, not a closed day."""
    prod = product()
    completed_sale(org, prod, price="5000", when=timezone.now())

    cashier = person(org, "till", "sale.create")
    payload = moduleinsights.insights_for(cashier, "retail")
    trend = payload["trend"]
    assert payload["trend_series"] == ["Revenue"]
    assert len(trend) == 14
    assert trend[-1]["values"] == [5000.0]
    assert trend[0]["values"] == [0.0]


def test_receivables_are_aged_not_merely_totalled(org):
    """How long it has been owed is what decides who gets chased."""
    for days, amount in ((-5, "100"), (10, "200"), (45, "300"), (120, "400")):
        CustomerInvoice.objects.create(
            organization=org,
            customer=org,
            invoice_number=f"INV-{days}",
            invoice_date=today() - timedelta(days=max(days, 0)),
            due_date=today() - timedelta(days=days),
            total_amount=Decimal(amount),
            amount_paid=Decimal("0"),
            status=CustomerInvoice.Status.OPEN,
        )

    accountant = person(org, "books", "finance.view")
    donuts = moduleinsights.insights_for(accountant, "finance")["donuts"]
    donut = next(d for d in donuts if "by age" in d["title"])
    assert {s["label"]: s["value"] for s in donut["slices"]} == {
        "Not yet due": 100.0,
        "1-30 days": 200.0,
        "31-60 days": 300.0,
        "Over 60 days": 400.0,
    }


def test_an_empty_ageing_chart_is_not_drawn_at_all(org):
    """A pharmacy with no credit customers should not be shown a blank pie."""
    accountant = person(org, "books", "finance.view")
    titles = [d["title"] for d in moduleinsights.insights_for(accountant, "finance")["donuts"]]
    assert not any("by age" in t for t in titles)


def test_the_ledger_reports_its_shape_even_with_no_receivables(org):
    """The complaint that started this: Finance looked empty while the books were not.

    Two posted entries are enough for the balance-sheet composition and the
    source breakdown to say something, so the home is never blank when the
    ledger is not.
    """
    cash = Account.objects.create(
        organization=org, code="1000", name="Cash", account_type=Account.Type.ASSET
    )
    sales = Account.objects.create(
        organization=org, code="4000", name="Sales", account_type=Account.Type.REVENUE
    )
    entry = JournalEntry.objects.create(
        organization=org,
        entry_number="JE-1",
        entry_date=today(),
        status=JournalEntry.Status.POSTED,
        source_module="SALES",
    )
    JournalLine.objects.create(
        entry=entry, account=cash, side=JournalLine.Side.DEBIT, amount=Decimal("5000")
    )
    JournalLine.objects.create(
        entry=entry, account=sales, side=JournalLine.Side.CREDIT, amount=Decimal("5000")
    )

    payload = moduleinsights.insights_for(person(org, "books", "finance.view"), "finance")
    sits = next(d for d in payload["donuts"] if d["title"] == "Where the money sits")
    assert {s["label"]: s["value"] for s in sits["slices"]} == {"Assets": 5000.0}
    produced = next(d for d in payload["donuts"] if "produced" in d["title"])
    assert {s["label"]: s["value"] for s in produced["slices"]} == {"Sales": 1}
    assert {t["label"]: t["value"] for t in payload["tiles"]}["Revenue posted"] == 5000.0
    assert payload["bars"][0]["data"], "the largest movements are always answerable"


def test_a_fully_paid_invoice_is_not_owed(org):
    CustomerInvoice.objects.create(
        organization=org,
        customer=org,
        invoice_number="INV-PAID",
        invoice_date=today(),
        due_date=today(),
        total_amount=Decimal("900"),
        amount_paid=Decimal("900"),
        status=CustomerInvoice.Status.PAID,
    )
    accountant = person(org, "books", "finance.view")
    tiles = {
        t["label"]: t["value"] for t in moduleinsights.insights_for(accountant, "finance")["tiles"]
    }
    assert tiles["Owed to us"] == 0.0


def test_only_posted_entries_count_as_spend(org):
    """A reversed entry is not money that went anywhere."""
    account = Account.objects.create(
        organization=org, code="5100", name="Rent", account_type=Account.Type.EXPENSE
    )
    for status, amount in (
        (JournalEntry.Status.POSTED, "700"),
        (JournalEntry.Status.REVERSED, "900"),
    ):
        entry = JournalEntry.objects.create(
            organization=org, entry_number=f"JE-{status}", entry_date=today(), status=status
        )
        JournalLine.objects.create(
            entry=entry, account=account, side=JournalLine.Side.DEBIT, amount=Decimal(amount)
        )

    accountant = person(org, "books", "finance.view")
    bars = moduleinsights.insights_for(accountant, "finance")["bars"][0]["data"]
    assert bars == [{"label": "Rent", "value": 700.0, "note": "Expense"}]


def test_claim_rejection_reasons_are_broken_out(org):
    """Each reason has a different remedy — the total alone tells you nothing."""
    scheme = InsuranceScheme.objects.create(organization=org, code="CBHI", name="CBHI")
    policy = MemberPolicy.objects.create(
        scheme=scheme,
        member_number="M1",
        full_name="Jean",
        valid_from=today() - timedelta(days=30),
        valid_to=today() + timedelta(days=300),
    )
    prod = product()
    for reason in ("Expired policy", "Expired policy", "Missing prescription"):
        Claim.objects.create(
            organization=org,
            scheme=scheme,
            policy=policy,
            sale=completed_sale(org, prod),
            claim_number=f"C{Claim.objects.count()}",
            service_date=today(),
            claimed_amount=Decimal("1000"),
            status=Claim.Status.REJECTED,
            rejection_reason=reason,
        )

    officer = person(org, "claims", "insurance.view")
    donuts = moduleinsights.insights_for(officer, "insurance")["donuts"]
    reasons = next(d for d in donuts if "rejected" in d["title"])
    assert {s["label"]: s["value"] for s in reasons["slices"]} == {
        "Expired Policy": 2,
        "Missing Prescription": 1,
    }


def test_medicines_stocked_never_exceeds_the_catalogue(org):
    """Counting shelf listings made a branch network look like a bigger catalogue."""
    prod = product()
    other = Organization.objects.create(name="Kicukiro", type="RETAIL")
    from apps.inventory.models import PharmacyProduct

    for o in (org, other):
        PharmacyProduct.objects.create(
            organization=o, product=prod, retail_price=Decimal("100"), is_active=True
        )

    viewer = person(org, "cat", "catalog.view")
    tiles = {
        t["label"]: t["value"] for t in moduleinsights.insights_for(viewer, "catalog")["tiles"]
    }
    assert tiles["Medicines stocked"] <= tiles["In the catalogue"]


# ---------------------------------------------------------------------------
# Over HTTP — the screen reaches it the same way
# ---------------------------------------------------------------------------


def test_the_endpoint_answers_for_a_named_module(org):
    prod = product()
    batch(org, prod, qty=5, cost="200")
    client = APIClient()
    client.force_authenticate(user=person(org, "keeper", "inventory.view"))

    resp = client.get("/api/workspace/module-insights/?module=inventory")
    assert resp.status_code == 200, resp.content
    assert set(resp.json()) == SHAPE


def test_the_endpoint_requires_a_login(org):
    assert APIClient().get("/api/workspace/module-insights/?module=retail").status_code in (
        401,
        403,
    )


def test_a_missing_module_parameter_is_empty_not_a_crash(org):
    client = APIClient()
    client.force_authenticate(user=person(org, "someone"))
    resp = client.get("/api/workspace/module-insights/")
    assert resp.status_code == 200
    assert resp.json()["tiles"] == []
