"""F2-rest — the additional first-class events.

Each publisher helper is exercised against the outbox model directly
(``publish()`` outside a transaction writes the row immediately — see
``apps/events/outbox.py``); the service-level integration is covered by
the existing sales / payroll / inventory service tests since they all
go through the same ``transaction.on_commit`` plumbing.

Idempotency is per ``(event_type, source_doc_type, source_doc_id,
source_line_id)``; we use unique ``source_doc_id`` values across tests
so we can assert a specific row lands.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events.events import EventType
from apps.events.models import OutboxEvent
from apps.events.publishers import (
    publish_fiscal_period_event,
    publish_inventory_adjusted,
    publish_statutory_payment_confirmed,
    publish_stock_disposed,
)
from apps.iam.models import Organization

# ``transaction=True``: publish() defers its write to transaction.on_commit
# whenever it is inside an atomic block, and pytest-django's default fixture
# wraps every test in one that never commits — so the rows would never appear.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def org() -> Organization:
    return Organization.objects.create(
        name="F2 Org",
        type=Organization.OrgType.RETAIL,
    )


# ---------------------------------------------------------------------------
# STATUTORY_PAYMENT_CONFIRMED — payload + source-doc tuple
# ---------------------------------------------------------------------------


def test_publish_statutory_payment_confirmed_writes_event(org):
    publish_statutory_payment_confirmed(
        organization=org,
        user=None,
        payment_id=42,
        amount=Decimal("12345.67"),
        period_start=str(date(2026, 7, 1)),
        period_end=str(date(2026, 7, 31)),
        rra_reference="RRA/2026/0001",
    )
    e = OutboxEvent.objects.get(event_type=EventType.STATUTORY_PAYMENT_CONFIRMED)
    assert e.organization_id == org.pk
    assert e.source_doc_type == "finance.TaxPayment"
    assert e.source_doc_id == "42"
    assert e.payload["amount"] == "12345.67"
    assert e.payload["period_start"] == "2026-07-01"
    assert e.payload["period_end"] == "2026-07-31"
    assert e.payload["rra_reference"] == "RRA/2026/0001"


# ---------------------------------------------------------------------------
# INVENTORY_ADJUSTED — delta + amount + sign
# ---------------------------------------------------------------------------


def test_publish_inventory_adjusted_negative_delta(org):
    publish_inventory_adjusted(
        organization=org,
        user=None,
        batch_id=99,
        product_id=7,
        delta=-3,
        amount=Decimal("1050.00"),
        reason="SC-2026-001 shrinkage",
        reference_type="stock_count",
        reference_id="99",
    )
    e = OutboxEvent.objects.get(event_type=EventType.INVENTORY_ADJUSTED)
    assert e.source_doc_type == "stock_count"
    assert e.payload["delta"] == -3
    assert e.payload["amount"] == "1050.00"
    assert e.payload["batch_id"] == "99"


def test_publish_inventory_adjusted_zero_amount_when_cost_unknown(org):
    publish_inventory_adjusted(
        organization=org,
        user=None,
        batch_id=99,
        product_id=7,
        delta=2,
        amount=None,
        reason="SC-2026-002 found",
        reference_type="stock_count",
        reference_id="100",
    )
    e = OutboxEvent.objects.get(event_type=EventType.INVENTORY_ADJUSTED)
    assert e.payload["amount"] is None
    assert e.payload["delta"] == 2


# ---------------------------------------------------------------------------
# STOCK_DISPOSED — quantity * cost + reason + reference
# ---------------------------------------------------------------------------


def test_publish_stock_disposed(org):
    publish_stock_disposed(
        organization=org,
        user=None,
        batch_id=12,
        product_id=3,
        quantity=4,
        amount=Decimal("1800.00"),
        reason="Damaged in transit",
        reference_type="wastage",
        reference_id="W-2026-7",
    )
    e = OutboxEvent.objects.get(event_type=EventType.STOCK_DISPOSED)
    assert e.source_doc_type == "wastage"
    assert e.source_doc_id == "W-2026-7"
    assert e.payload["quantity"] == 4
    assert e.payload["amount"] == "1800.00"
    assert e.payload["reason"] == "Damaged in transit"


# ---------------------------------------------------------------------------
# FISCAL_PERIOD events — the close / reopen variants
# ---------------------------------------------------------------------------


def test_publish_fiscal_period_closed(org):
    publish_fiscal_period_event(
        event=EventType.FISCAL_PERIOD_CLOSED,
        period_id=1,
        organization=org,
        user=None,
        kind="MONTH",
        start_date=str(date(2026, 7, 1)),
        end_date=str(date(2026, 7, 31)),
    )
    e = OutboxEvent.objects.get(event_type=EventType.FISCAL_PERIOD_CLOSED)
    assert e.payload["kind"] == "MONTH"
    assert e.payload["start_date"] == "2026-07-01"
    assert e.payload["end_date"] == "2026-07-31"


def test_publish_eom_close_finalised(org):
    publish_fiscal_period_event(
        event=EventType.EOM_CLOSE_FINALISED,
        period_id=2,
        organization=org,
        user=None,
        kind="MONTH",
        start_date=str(date(2026, 7, 1)),
        end_date=str(date(2026, 7, 31)),
    )
    e = OutboxEvent.objects.get(event_type=EventType.EOM_CLOSE_FINALISED)
    assert e.payload["period_id"] == "2"


def test_publish_period_reopened(org):
    publish_fiscal_period_event(
        event=EventType.PERIOD_REOPENED,
        period_id=3,
        organization=org,
        user=None,
        kind="MONTH",
        start_date=str(date(2026, 6, 1)),
        end_date=str(date(2026, 6, 30)),
    )
    e = OutboxEvent.objects.get(event_type=EventType.PERIOD_REOPENED)
    assert e.source_doc_id == "3"


# ---------------------------------------------------------------------------
# Idempotency contract — two publishes for the same logical event collapse.
# ---------------------------------------------------------------------------


def test_publishers_are_idempotent_on_source_doc_tuple(org):
    """A re-run of the same business action must not produce a second row."""
    payload = {
        "organization": org,
        "user": None,
        "payment_id": 500,
        "amount": Decimal("7777.00"),
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "rra_reference": "",
    }
    publish_statutory_payment_confirmed(**payload)
    # Same logical event — must raise on the unique constraint (the second
    # ``OutboxEvent.objects.create`` would also fail, but we exercise the
    # publisher path which goes through on_commit; here we replicate the
    # direct row write).
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        OutboxEvent.objects.create(
            event_type=EventType.STATUTORY_PAYMENT_CONFIRMED,
            payload={"amount": "7777.00"},
            source_doc_type="finance.TaxPayment",
            source_doc_id="500",
            organization=org,
        )
