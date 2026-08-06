"""Tests for the OutboxEvent model and the ``outbox.publish`` API.

The outbox pattern is the cross-cutting primitive for every other module —
getting these tests right protects every downstream integration.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.events.events import EventType
from apps.events.models import OutboxEvent
from apps.events.outbox import publish, subscribe

pytestmark = pytest.mark.django_db


def test_publish_outside_atomic_writes_immediately(organization, user):
    """Without ``transaction.atomic`` the row is written straight away."""
    ev = publish(
        event_type=EventType.SALE_FINALISED,
        payload={"sale_id": 123, "total": "1500.00"},
        source_doc_type="retail.Sale",
        source_doc_id=123,
        organization_id=organization.pk,
        user=user,
    )
    assert ev is not None
    assert ev.pk is not None
    assert ev.status == OutboxEvent.Status.PENDING
    assert ev.payload["total"] == "1500.00"
    assert ev.source_doc_id == "123"


def test_publish_inside_atomic_defers_until_commit(organization):
    """Inside atomic(): no row until commit."""
    captured = {}

    with transaction.atomic():
        publish(
            event_type=EventType.STOCK_ORDER_APPROVED,
            source_doc_type="distribution.StockOrder",
            source_doc_id=999,
            organization_id=organization.pk,
        )
        # Not visible yet — on_commit hasn't fired.
        assert OutboxEvent.objects.count() == 0
        captured["inside_count"] = 0

    # After commit the row exists.
    assert OutboxEvent.objects.count() == 1
    assert captured["inside_count"] == 0


def test_publish_inside_atomic_aborts_when_transaction_rolls_back(organization):
    """A rolled-back transaction must leave no event (the whole point of the pattern)."""
    try:
        with transaction.atomic():
            publish(
                event_type=EventType.PAYMENT_RECEIVED,
                source_doc_type="finance.CustomerReceipt",
                source_doc_id=42,
                organization_id=organization.pk,
            )
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    assert OutboxEvent.objects.count() == 0


def test_unique_constraint_prevents_duplicate_logical_events(organization):
    """Two publishes for the same logical event must collapse to one row.

    This is the contract that makes dispatcher retries safe: replays happen
    *on the same row*, never as new rows.
    """
    OutboxEvent.objects.create(
        event_type=EventType.SALE_FINALISED,
        payload={"first": True},
        source_doc_type="retail.Sale",
        source_doc_id="555",
        organization=organization,
    )
    with pytest.raises(IntegrityError):
        OutboxEvent.objects.create(
            event_type=EventType.SALE_FINALISED,
            payload={"second": True},
            source_doc_type="retail.Sale",
            source_doc_id="555",
            organization=organization,
        )


def test_empty_source_ids_still_unique_per_event_type(organization):
    """Two publishes with no source ids are still distinct events (different pk)."""
    a = OutboxEvent.objects.create(
        event_type=EventType.FISCAL_PERIOD_OPENED,
        source_doc_type="",
        source_doc_id="",
        organization=organization,
    )
    b = OutboxEvent.objects.create(
        event_type=EventType.FISCAL_PERIOD_OPENED,
        source_doc_type="",
        source_doc_id="",
        organization=organization,
    )
    # Different rows, both PENDING — the unique constraint permits two events
    # with no source because the four-tuple is (event_type, "", "", "").
    assert a.pk != b.pk


def test_subscribe_and_get_handlers_returns_registered_handlers():
    """The in-process handler registry is keyed by event_type."""
    calls = []

    def h1(ev):
        calls.append(("h1", ev.pk))

    def h2(ev):
        calls.append(("h2", ev.pk))

    subscribe(EventType.PAYROLL_RUN_APPROVED, h1)
    subscribe(EventType.PAYROLL_RUN_APPROVED, h2)
    subscribe(EventType.SALE_FINALISED, h1)

    payroll_handlers = subscribe  # noqa - just to keep lint happy
    from apps.events.outbox import get_handlers

    assert len(get_handlers(EventType.PAYROLL_RUN_APPROVED)) == 2
    assert len(get_handlers(EventType.SALE_FINALISED)) == 1
    assert get_handlers("NoSuchEvent") == []


def test_event_type_choices_are_stable_strings():
    """TextChoices values are the on-wire strings — changing them is a break."""
    assert EventType.SALE_FINALISED == "SaleFinalised"
    assert EventType.PAYROLL_RUN_APPROVED == "PayrollRunApproved"
    assert EventType.APPROVAL_REQUESTED == "ApprovalRequested"