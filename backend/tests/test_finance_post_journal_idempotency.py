"""Tests for post_journal idempotency (F1.2 — ADR-011 contract).

A re-run of post_journal with the same (organization, reference_type,
reference_id) must return the same JournalEntry, not create a duplicate.
Manual / adjustment postings (no reference_type) keep their old behaviour.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.finance.models import Account, JournalEntry
from apps.finance.services import post_journal

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_accounts(organization):
    """A minimal pair of accounts to balance a journal against."""
    cash = Account.objects.create(
        organization=organization,
        code="1000",
        name="Cash & Bank",
        account_type=Account.Type.ASSET,
        normal_balance=Account.Balance.DEBIT,
        is_system=True,
    )
    revenue = Account.objects.create(
        organization=organization,
        code="4000",
        name="Sales Revenue",
        account_type=Account.Type.REVENUE,
        normal_balance=Account.Balance.CREDIT,
    )
    return cash, revenue


def _balanced_lines(cash, revenue, amount="1500.00"):
    return [
        {"account": cash, "side": "DEBIT", "amount": Decimal(amount), "memo": ""},
        {"account": revenue, "side": "CREDIT", "amount": Decimal(amount), "memo": ""},
    ]


def test_post_journal_creates_entry_when_reference_is_new(organization, org_accounts):
    cash, revenue = org_accounts
    entry = post_journal(
        organization=organization,
        description="Sale #1001",
        lines=_balanced_lines(cash, revenue),
        reference_type="retail.Sale",
        reference_id="1001",
    )
    assert entry.pk is not None
    assert JournalEntry.objects.filter(pk=entry.pk).exists()


def test_post_journal_is_idempotent_on_same_reference(organization, org_accounts):
    """Re-running post_journal with the same source doc returns the SAME entry."""
    cash, revenue = org_accounts
    first = post_journal(
        organization=organization,
        description="Sale #1002",
        lines=_balanced_lines(cash, revenue),
        reference_type="retail.Sale",
        reference_id="1002",
    )
    second = post_journal(
        organization=organization,
        description="Sale #1002 (retry)",
        lines=_balanced_lines(cash, revenue),
        reference_type="retail.Sale",
        reference_id="1002",
    )
    assert first.pk == second.pk
    assert JournalEntry.objects.filter(reference_id="1002").count() == 1


def test_post_journal_does_not_dedupe_manual_postings(organization, org_accounts):
    """An empty ``reference_type`` is a manual / adjustment — must NOT collapse."""
    cash, revenue = org_accounts
    a = post_journal(
        organization=organization,
        description="Manual adjustment 1",
        lines=_balanced_lines(cash, revenue, amount="10.00"),
        reference_type="",
        reference_id="",
    )
    b = post_journal(
        organization=organization,
        description="Manual adjustment 2",
        lines=_balanced_lines(cash, revenue, amount="20.00"),
        reference_type="",
        reference_id="",
    )
    assert a.pk != b.pk


def test_post_journal_same_reference_different_org_is_allowed(organization, org_accounts):
    """Idempotency is per-organization — two tenants may share a doc id."""
    cash, revenue = org_accounts
    from apps.iam.models import Organization

    other = Organization.objects.create(
        name="Other Pharmacy Ltd",
        type=Organization.OrgType.RETAIL,
    )
    a = post_journal(
        organization=organization,
        description="Sale in org A",
        lines=_balanced_lines(cash, revenue),
        reference_type="retail.Sale",
        reference_id="42",
    )
    other_cash = Account.objects.create(
        organization=other,
        code="1000",
        name="Cash & Bank",
        account_type=Account.Type.ASSET,
        normal_balance=Account.Balance.DEBIT,
        is_system=True,
    )
    other_rev = Account.objects.create(
        organization=other,
        code="4000",
        name="Sales Revenue",
        account_type=Account.Type.REVENUE,
        normal_balance=Account.Balance.CREDIT,
    )
    b = post_journal(
        organization=other,
        description="Sale in org B",
        lines=_balanced_lines(other_cash, other_rev),
        reference_type="retail.Sale",
        reference_id="42",
    )
    assert a.pk != b.pk