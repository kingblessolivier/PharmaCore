"""Finance statements: trial balance, P&L, balance sheet, cash-flow, the
performance cockpit, HQ consolidation, and EOD/EOM period close.

These assert accounting *correctness*, not just that endpoints answer: the trial
balance must balance, the balance sheet must satisfy A = L + E, margins must match
hand-computed values, and a closed period must actually refuse new postings.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.finance import reports
from apps.finance.models import Account, AccountingPeriod
from apps.finance.services import (
    PeriodClosedError,
    close_period,
    ensure_default_accounts,
    post_journal,
    reopen_period,
)
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient

JAN = date(2026, 1, 1)
JAN_END = date(2026, 1, 31)


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Branch", type="RETAIL")


@pytest.fixture
def accountant(org: Organization) -> User:
    u = User.objects.create_user(username="reporter", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return u


@pytest.fixture
def traded(org: Organization) -> dict[str, Account]:
    """A month of real trading: capital in, a sale, its cost, and an expense."""
    acc = ensure_default_accounts(org)
    # Owner puts in 1,000,000.
    post_journal(
        organization=org,
        entry_date=JAN,
        description="Capital introduced",
        lines=[
            {"account": acc["1000"], "side": "DEBIT", "amount": Decimal("1000000"), "memo": ""},
            {"account": acc["3000"], "side": "CREDIT", "amount": Decimal("1000000"), "memo": ""},
        ],
    )
    # Sale of 400,000 on credit.
    post_journal(
        organization=org,
        entry_date=date(2026, 1, 10),
        description="Sale",
        lines=[
            {"account": acc["1100"], "side": "DEBIT", "amount": Decimal("400000"), "memo": ""},
            {"account": acc["4000"], "side": "CREDIT", "amount": Decimal("400000"), "memo": ""},
        ],
    )
    # Its cost of goods, 250,000.
    post_journal(
        organization=org,
        entry_date=date(2026, 1, 10),
        description="COGS",
        lines=[
            {"account": acc["5000"], "side": "DEBIT", "amount": Decimal("250000"), "memo": ""},
            {"account": acc["2000"], "side": "CREDIT", "amount": Decimal("250000"), "memo": ""},
        ],
    )
    # Salaries paid in cash, 50,000 (an operating expense).
    post_journal(
        organization=org,
        entry_date=date(2026, 1, 25),
        description="Salaries",
        lines=[
            {"account": acc["6000"], "side": "DEBIT", "amount": Decimal("50000"), "memo": ""},
            {"account": acc["1000"], "side": "CREDIT", "amount": Decimal("50000"), "memo": ""},
        ],
    )
    return acc


@pytest.mark.django_db
def test_trial_balance_balances(org: Organization, traded: dict[str, Account]) -> None:
    tb = reports.trial_balance(org, as_of=JAN_END)
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]
    # 1,000,000 + 400,000 + 250,000 + 50,000 of debits were posted.
    assert tb["total_debit"] == Decimal("1700000.00")


@pytest.mark.django_db
def test_profit_and_loss_margins(org: Organization, traded: dict[str, Account]) -> None:
    pl = reports.profit_and_loss(org, start=JAN, end=JAN_END)
    assert pl["revenue"] == Decimal("400000.00")
    assert pl["cogs"] == Decimal("250000.00")
    assert pl["gross_profit"] == Decimal("150000.00")
    # 150,000 / 400,000 = 37.5%
    assert pl["gross_margin_pct"] == Decimal("37.50")
    assert pl["operating_expenses"] == Decimal("50000.00")
    assert pl["net_profit"] == Decimal("100000.00")
    # 100,000 / 400,000 = 25%
    assert pl["net_margin_pct"] == Decimal("25.00")


@pytest.mark.django_db
def test_balance_sheet_satisfies_accounting_equation(
    org: Organization, traded: dict[str, Account]
) -> None:
    bs = reports.balance_sheet(org, as_of=JAN_END)
    # Cash 950,000 + AR 400,000 = 1,350,000
    assert bs["total_assets"] == Decimal("1350000.00")
    # AP 250,000
    assert bs["total_liabilities"] == Decimal("250000.00")
    # Capital 1,000,000 + retained earnings 100,000
    assert bs["contributed_equity"] == Decimal("1000000.00")
    assert bs["retained_earnings"] == Decimal("100000.00")
    assert bs["total_equity"] == Decimal("1100000.00")
    assert bs["balanced"] is True


@pytest.mark.django_db
def test_cash_flow_classifies_by_contra_account(
    org: Organization, traded: dict[str, Account]
) -> None:
    cf = reports.cash_flow_statement(org, start=JAN, end=JAN_END)
    # Capital introduction is financing; salary payment is operating.
    assert cf["financing"] == Decimal("1000000.00")
    assert cf["operating"] == Decimal("-50000.00")
    assert cf["net_change"] == Decimal("950000.00")
    assert cf["opening_cash"] == Decimal("0.00")
    assert cf["closing_cash"] == Decimal("950000.00")


@pytest.mark.django_db
def test_performance_compares_with_previous_period(
    org: Organization, traded: dict[str, Account]
) -> None:
    perf = reports.performance(org, start=JAN, end=JAN_END)
    assert perf["revenue"] == Decimal("400000.00")
    assert perf["gross_margin_pct"] == Decimal("37.50")
    assert perf["receivable"] == Decimal("400000.00")
    # December had no trading, so there is no meaningful percentage to show.
    assert perf["previous"]["revenue"] == Decimal("0.00")
    assert perf["delta_pct"]["revenue"] is None
    # DSO = 400,000 / 400,000 * 31 days
    assert perf["dso_days"] == Decimal("31.00")


@pytest.mark.django_db
def test_consolidation_sums_branches_and_keeps_each_visible(
    org: Organization, traded: dict[str, Account]
) -> None:
    other = Organization.objects.create(name="Huye Branch", type="RETAIL")
    acc2 = ensure_default_accounts(other)
    post_journal(
        organization=other,
        entry_date=date(2026, 1, 5),
        description="Sale",
        lines=[
            {"account": acc2["1000"], "side": "DEBIT", "amount": Decimal("100000"), "memo": ""},
            {"account": acc2["4000"], "side": "CREDIT", "amount": Decimal("100000"), "memo": ""},
        ],
    )
    group = reports.consolidated([org, other], start=JAN, end=JAN_END)
    assert group["totals"]["revenue"] == Decimal("500000.00")
    assert len(group["branches"]) == 2
    by_name = {b["organization_name"]: b for b in group["branches"]}
    assert by_name["Huye Branch"]["revenue"] == Decimal("100000.00")
    assert by_name["Kigali Branch"]["revenue"] == Decimal("400000.00")


@pytest.mark.django_db
def test_closed_period_refuses_new_postings(
    org: Organization, traded: dict[str, Account], accountant: User
) -> None:
    period = close_period(
        organization=org,
        kind=AccountingPeriod.Kind.MONTH,
        start_date=JAN,
        end_date=JAN_END,
        user=accountant,
    )
    assert period.status == AccountingPeriod.Status.CLOSED
    # The headline figures are frozen onto the record.
    assert period.closing_totals["net_profit"] == "100000.00"

    with pytest.raises(PeriodClosedError):
        post_journal(
            organization=org,
            entry_date=date(2026, 1, 15),
            description="Late entry into a closed month",
            lines=[
                {"account": traded["1000"], "side": "DEBIT", "amount": Decimal("1"), "memo": ""},
                {"account": traded["3000"], "side": "CREDIT", "amount": Decimal("1"), "memo": ""},
            ],
        )

    # A date outside the closed window is still fine.
    post_journal(
        organization=org,
        entry_date=date(2026, 2, 1),
        description="February entry",
        lines=[
            {"account": traded["1000"], "side": "DEBIT", "amount": Decimal("1"), "memo": ""},
            {"account": traded["3000"], "side": "CREDIT", "amount": Decimal("1"), "memo": ""},
        ],
    )


@pytest.mark.django_db
def test_reopen_requires_a_reason_and_restores_posting(
    org: Organization, traded: dict[str, Account], accountant: User
) -> None:
    period = close_period(
        organization=org,
        kind=AccountingPeriod.Kind.MONTH,
        start_date=JAN,
        end_date=JAN_END,
        user=accountant,
    )
    with pytest.raises(ValueError):
        reopen_period(period=period, user=accountant, reason="   ")

    reopen_period(period=period, user=accountant, reason="Missing supplier invoice found")
    post_journal(
        organization=org,
        entry_date=date(2026, 1, 15),
        description="Now allowed",
        lines=[
            {"account": traded["1000"], "side": "DEBIT", "amount": Decimal("1"), "memo": ""},
            {"account": traded["3000"], "side": "CREDIT", "amount": Decimal("1"), "memo": ""},
        ],
    )


@pytest.mark.django_db
def test_reports_api_endpoints(
    org: Organization, traded: dict[str, Account], accountant: User
) -> None:
    client = _auth(accountant)
    qs = f"?organization={org.pk}&start={JAN}&end={JAN_END}"

    tb = client.get(f"/api/finance/reports/trial-balance/?organization={org.pk}&as_of={JAN_END}")
    assert tb.status_code == 200, tb.content
    assert tb.json()["balanced"] is True

    pl = client.get(f"/api/finance/reports/profit-and-loss/{qs}")
    assert pl.status_code == 200
    assert Decimal(pl.json()["gross_margin_pct"]) == Decimal("37.50")

    bs = client.get(f"/api/finance/reports/balance-sheet/?organization={org.pk}&as_of={JAN_END}")
    assert bs.status_code == 200
    assert bs.json()["balanced"] is True

    cf = client.get(f"/api/finance/reports/cash-flow/{qs}")
    assert cf.status_code == 200
    assert Decimal(cf.json()["closing_cash"]) == Decimal("950000.00")

    perf = client.get(f"/api/finance/reports/performance/{qs}")
    assert perf.status_code == 200
    assert "series" in perf.json()

    group = client.get(f"/api/finance/reports/consolidated/{qs}")
    assert group.status_code == 200
    assert group.json()["totals"]["revenue"] == "400000.00"


@pytest.mark.django_db
def test_period_close_api(org: Organization, traded: dict[str, Account], accountant: User) -> None:
    resp = _auth(accountant).post(
        f"/api/finance/periods/?organization={org.pk}",
        {"kind": "MONTH", "start_date": str(JAN), "end_date": str(JAN_END)},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["status"] == "CLOSED"
    period_id = resp.json()["id"]

    # Closing twice is refused.
    again = _auth(accountant).post(
        f"/api/finance/periods/?organization={org.pk}",
        {"kind": "MONTH", "start_date": str(JAN), "end_date": str(JAN_END)},
        format="json",
    )
    assert again.status_code == 400

    reopened = _auth(accountant).post(
        f"/api/finance/periods/{period_id}/reopen/", {"reason": "correction"}, format="json"
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "OPEN"
