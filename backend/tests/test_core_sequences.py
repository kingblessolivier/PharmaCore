"""Tests for apps.core.sequences.next_number (F4.2).

The helper is the one numbering primitive every module will call. These
tests guard against:
- Two threads getting the same number
- Rolling back a transaction returning the number to the pool
- Different (org, domain, kind, year) tuples not colliding
"""

from __future__ import annotations

import threading

import pytest
from django.db import connections, transaction

from apps.core.sequences import next_document_number, next_number
from apps.iam.models import Organization
from apps.procurement.models import NumberSequence

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization(db: None) -> Organization:
    return Organization.objects.create(name="Sequence Test Depot", type="DEPOT")


def test_first_call_returns_one(organization):
    with transaction.atomic():
        n = next_number(
            organization=organization,
            domain=NumberSequence.Domain.FINANCE,
            kind=NumberSequence.Kind.JOURNAL_ENTRY,
        )
    assert n == 1


def test_sequential_calls_return_monotonic_increasing_numbers(organization):
    nums = []
    for _ in range(5):
        with transaction.atomic():
            nums.append(
                next_number(
                    organization=organization,
                    domain=NumberSequence.Domain.HR,
                    kind=NumberSequence.Kind.PAYSLIP,
                )
            )
    assert nums == [1, 2, 3, 4, 5]


def test_rolling_back_returns_number_to_pool(organization):
    """If the consuming insert fails, the allocated number must be reusable."""
    try:
        with transaction.atomic():
            n = next_number(
                organization=organization,
                domain=NumberSequence.Domain.RETAIL,
                kind=NumberSequence.Kind.CUSTOMER_RECEIPT,
            )
            assert n == 1
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    # After rollback the next allocation is 1 again — the bump was rolled back.
    with transaction.atomic():
        again = next_number(
            organization=organization,
            domain=NumberSequence.Domain.RETAIL,
            kind=NumberSequence.Kind.CUSTOMER_RECEIPT,
        )
    assert again == 1


def test_different_domains_have_independent_counters(organization):
    """Finance journals and HR payslips don't collide."""
    with transaction.atomic():
        je = next_number(
            organization=organization,
            domain=NumberSequence.Domain.FINANCE,
            kind=NumberSequence.Kind.JOURNAL_ENTRY,
        )
    with transaction.atomic():
        ps = next_number(
            organization=organization,
            domain=NumberSequence.Domain.HR,
            kind=NumberSequence.Kind.PAYSLIP,
        )
    assert je == 1
    assert ps == 1


def test_different_years_have_independent_counters(organization):
    with transaction.atomic():
        a = next_number(
            organization=organization,
            domain=NumberSequence.Domain.FINANCE,
            kind=NumberSequence.Kind.STATUTORY_FILING,
            year=2025,
        )
    with transaction.atomic():
        b = next_number(
            organization=organization,
            domain=NumberSequence.Domain.FINANCE,
            kind=NumberSequence.Kind.STATUTORY_FILING,
            year=2026,
        )
    assert a == 1
    assert b == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connections["default"].vendor == "sqlite",
    reason=(
        "SQLite locks the whole file for writes, so concurrent worker threads "
        "raise 'database table is locked' rather than exercising the row lock. "
        "The guarantee under test is a Postgres SELECT FOR UPDATE."
    ),
)
def test_concurrent_threads_get_unique_numbers(organization):
    """Two threads racing on the same sequence must not collide."""
    NUM_THREADS = 10
    results: list[int] = []
    lock = threading.Lock()

    def worker():
        # Each thread opens its own DB connection.
        with transaction.atomic():
            n = next_number(
                organization=organization,
                domain=NumberSequence.Domain.INVENTORY,
                kind=NumberSequence.Kind.GOODS_RECEIPT,
            )
            with lock:
                results.append(n)
            # Close the per-thread connection so pytest-django can clean up.
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All results are unique.
    assert len(set(results)) == NUM_THREADS


def test_next_document_number_returns_formatted_string(organization):
    s = next_document_number(
        organization=organization,
        domain=NumberSequence.Domain.PROCUREMENT,
        kind=NumberSequence.Kind.PURCHASE_ORDER,
    )
    assert s == "PO-2026-00001"


def test_next_document_number_respects_prefix_override(organization):
    s = next_document_number(
        organization=organization,
        domain=NumberSequence.Domain.FINANCE,
        kind=NumberSequence.Kind.CUSTOMER_INVOICE,
        prefix="AR-INV",
    )
    assert s.startswith("AR-INV-")
    assert s.endswith("-00001")
