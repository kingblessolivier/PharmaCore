"""Banking & cash: bank accounts with their own GL sub-ledger, the cash-book,
reconciliation, and a real cash-flow forecast built from AR/AP due dates."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Supplier
from apps.distribution.models import OrderItem, StockOrder
from apps.finance.models import BankAccount
from apps.finance.services import (
    cash_book_lines,
    cash_flow_forecast,
    create_bank_account,
    reconcile_lines,
    record_supplier_bill,
)
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Central Depot", type="DEPOT")


@pytest.fixture
def accountant(org: Organization) -> User:
    u = User.objects.create_user(username="bankclerk", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return u


@pytest.mark.django_db
def test_create_bank_account_opens_gl_subaccount_and_posts_opening_balance(
    org: Organization, accountant: User
) -> None:
    account = create_bank_account(
        organization=org,
        name="BK Kigali Current",
        kind=BankAccount.Kind.BANK,
        bank_name="Bank of Kigali",
        opening_balance=Decimal("500000"),
        user=accountant,
    )
    assert account.gl_account.code == "1000-01"
    assert account.gl_account.parent.code == "1000"
    rows = cash_book_lines(account)
    assert len(rows) == 1
    assert rows[0]["running_balance"] == Decimal("500000.00")


@pytest.mark.django_db
def test_second_bank_account_gets_distinct_subaccount(org: Organization, accountant: User) -> None:
    create_bank_account(
        organization=org, name="Bank A", kind=BankAccount.Kind.BANK, user=accountant
    )
    second = create_bank_account(
        organization=org, name="MoMo", kind=BankAccount.Kind.MOMO, user=accountant
    )
    assert second.gl_account.code == "1000-02"


@pytest.mark.django_db
def test_reconcile_lines_marks_matched(org: Organization, accountant: User) -> None:
    account = create_bank_account(
        organization=org,
        name="Cash drawer",
        kind=BankAccount.Kind.CASH,
        opening_balance=Decimal("1000"),
        user=accountant,
    )
    rows = cash_book_lines(account)
    line_id = rows[0]["line_id"]
    count = reconcile_lines(line_ids=[line_id], statement_reference="STMT-001", user=accountant)
    assert count == 1
    rows2 = cash_book_lines(account)
    assert rows2[0]["is_reconciled"] is True
    assert rows2[0]["statement_reference"] == "STMT-001"

    # Reconciling again does nothing (already reconciled).
    assert reconcile_lines(line_ids=[line_id], statement_reference="STMT-002", user=accountant) == 0


@pytest.mark.django_db
def test_bank_account_api_and_cash_book_endpoint(org: Organization, accountant: User) -> None:
    resp = _auth(accountant).post(
        "/api/finance/bank-accounts/",
        {
            "organization": org.pk,
            "name": "Main account",
            "kind": "BANK",
            "opening_balance": "200000",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    account_id = resp.json()["id"]

    cb = _auth(accountant).get(f"/api/finance/bank-accounts/{account_id}/cash-book/")
    assert cb.status_code == 200
    assert len(cb.json()) == 1
    # Money crosses the wire as a string — never a float, which would trade
    # exactness for binary floating point.
    assert cb.json()[0]["running_balance"] == "200000.00"

    line_id = cb.json()[0]["line_id"]
    rec = _auth(accountant).post(
        f"/api/finance/bank-accounts/{account_id}/reconcile/",
        {"line_ids": [line_id], "statement_reference": "JAN-STMT"},
        format="json",
    )
    assert rec.status_code == 200
    assert rec.json()["reconciled"] == 1


@pytest.mark.django_db
def test_cash_flow_forecast_buckets_ar_and_ap(org: Organization, accountant: User) -> None:
    from apps.catalog.models import Product

    retail = Organization.objects.create(name="Branch Pharmacy", type="RETAIL")
    product = Product.objects.create(generic_name="Paracetamol", strength="500mg")
    order = StockOrder.objects.create(
        depot=org,
        retail=retail,
        status=StockOrder.Status.DELIVERED,
        payment_due_date=date.today() + timedelta(days=10),
    )
    OrderItem.objects.create(order=order, product=product, quantity_ordered=10, price_per_unit=1000)

    supplier = Supplier.objects.create(name="Global Pharma Imports")
    record_supplier_bill(
        organization=org,
        supplier=supplier,
        bill_number="INV-1",
        bill_date=date.today(),
        due_date=date.today() + timedelta(days=45),
        total_amount=Decimal("30000"),
        user=accountant,
    )

    result = cash_flow_forecast(org)
    buckets = {row["bucket"]: row for row in result["projection"]}
    assert buckets["d30"]["inflows"] == Decimal("10000.00")
    assert buckets["d60"]["outflows"] == Decimal("30000.00")
