"""Finance: chart of accounts, balanced journals, auto-posting from B2B settlement,
and the approval-gated credit-override flow."""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import ApprovalError, claim, decide
from apps.catalog.models import Product
from apps.distribution.models import OrderItem, StockOrder
from apps.finance.models import Account, CreditProfile, JournalEntry
from apps.finance.services import ensure_default_accounts, post_journal
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Central Depot", type="DEPOT")


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Branch Pharmacy", type="RETAIL")


@pytest.fixture
def accountant(depot: Organization) -> User:
    u = User.objects.create_user(username="fin", password="x", organization=depot)
    u.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return u


@pytest.fixture
def senior(depot: Organization) -> User:
    u = User.objects.create_user(username="fsenior", password="x", organization=depot)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


@pytest.mark.django_db
def test_ensure_default_accounts_idempotent(depot: Organization) -> None:
    accounts = ensure_default_accounts(depot)
    assert accounts["1100"].name == "Cash on Hand"
    count_before = Account.objects.filter(organization=depot).count()
    ensure_default_accounts(depot)
    assert Account.objects.filter(organization=depot).count() == count_before


@pytest.mark.django_db
def test_post_journal_requires_balance(depot: Organization) -> None:
    accounts = ensure_default_accounts(depot)
    with pytest.raises(ValueError):
        post_journal(
            organization=depot,
            description="unbalanced",
            lines=[
                {"account": accounts["1100"], "side": "DEBIT", "amount": Decimal("10"), "memo": ""},
                {"account": accounts["1400"], "side": "CREDIT", "amount": Decimal("5"), "memo": ""},
            ],
        )


@pytest.mark.django_db
def test_post_journal_balanced_ok(depot: Organization) -> None:
    accounts = ensure_default_accounts(depot)
    entry = post_journal(
        organization=depot,
        description="opening",
        lines=[
            {"account": accounts["1100"], "side": "DEBIT", "amount": Decimal("100"), "memo": ""},
            {"account": accounts["3000"], "side": "CREDIT", "amount": Decimal("100"), "memo": ""},
        ],
    )
    assert entry.entry_number
    assert entry.total_debit == entry.total_credit == 100.0


@pytest.mark.django_db
def test_account_api_reports_balances_signed_to_normal_side(
    depot: Organization, accountant: User
) -> None:
    """A chart of accounts without balances isn't a chart of accounts. Each row
    carries its balance, signed so the account's own normal side reads positive:
    a debit-normal asset and a credit-normal equity account both show +100 for
    the two halves of the same entry."""
    accounts = ensure_default_accounts(depot)
    post_journal(
        organization=depot,
        description="opening",
        lines=[
            {"account": accounts["1100"], "side": "DEBIT", "amount": Decimal("100"), "memo": ""},
            {"account": accounts["3000"], "side": "CREDIT", "amount": Decimal("100"), "memo": ""},
        ],
    )
    resp = _auth(accountant).get(f"/api/finance/accounts/?organization={depot.pk}")
    assert resp.status_code == 200, resp.content
    by_code = {a["code"]: a for a in resp.json()["results"]}

    assert Decimal(by_code["1100"]["balance"]) == Decimal("100")  # debit-normal asset
    assert Decimal(by_code["3000"]["balance"]) == Decimal("100")  # credit-normal equity
    assert Decimal(by_code["1400"]["balance"]) == Decimal("0")  # untouched

    # The accounting identity holds across the whole chart: A = L + E + (Rev - Exp).
    def total(kind: str) -> Decimal:
        return sum(
            (Decimal(a["balance"]) for a in by_code.values() if a["account_type"] == kind),
            Decimal("0"),
        )

    assert total("ASSET") == total("LIABILITY") + total("EQUITY") + total("REVENUE") - total(
        "EXPENSE"
    )


@pytest.mark.django_db
def test_b2b_payment_auto_posts_both_books(
    depot: Organization, retail: Organization, accountant: User
) -> None:
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    order = StockOrder.objects.create(
        depot=depot, retail=retail, status=StockOrder.Status.DELIVERED
    )
    OrderItem.objects.create(order=order, product=product, quantity_ordered=10, price_per_unit=100)

    resp = _auth(accountant).post(
        f"/api/distribution/orders/{order.pk}/record-payment/",
        {"amount": "500", "method": "BANK_TRANSFER", "reference": "TXN1"},
    )
    assert resp.status_code == 200, resp.content

    depot_entries = JournalEntry.objects.filter(organization=depot)
    retail_entries = JournalEntry.objects.filter(organization=retail)
    assert depot_entries.count() == 1
    assert retail_entries.count() == 1
    assert depot_entries.first().total_debit == 500.0
    assert retail_entries.first().total_debit == 500.0


@pytest.mark.django_db
def test_credit_override_routes_through_approvals_and_no_self_approval(
    depot: Organization, retail: Organization, accountant: User, senior: User
) -> None:
    profile = CreditProfile.objects.create(creditor=depot, debtor=retail, credit_limit=1000)

    resp = _auth(accountant).post(
        f"/api/finance/credit-profiles/{profile.pk}/request-override/",
        {"credit_limit": "5000", "reason": "Retailer requested a higher limit"},
    )
    assert resp.status_code == 201, resp.content
    approval_id = resp.json()["approval_request"]

    # The limit must NOT have changed yet — it's pending approval.
    profile.refresh_from_db()
    assert profile.credit_limit == Decimal("1000")

    approval = ApprovalRequest.objects.get(pk=approval_id)
    # The requester (accountant) cannot approve their own override request.
    with pytest.raises(ApprovalError):
        claim(approval=approval, user=accountant)

    claim(approval=approval, user=senior)
    decide(approval=approval, user=senior, approve=True)

    profile.refresh_from_db()
    assert profile.credit_limit == Decimal("5000")


@pytest.mark.django_db
def test_credit_profile_limit_not_directly_patchable(
    depot: Organization, retail: Organization, accountant: User
) -> None:
    profile = CreditProfile.objects.create(creditor=depot, debtor=retail, credit_limit=1000)
    resp = _auth(accountant).patch(
        f"/api/finance/credit-profiles/{profile.pk}/", {"credit_limit": "99999"}, format="json"
    )
    # PATCH isn't even a permitted method — the only mutation path is request-override.
    assert resp.status_code == 405
