"""Tests for the outbox dispatcher command (F1.4).

The dispatcher is the consumer side of the bus. These tests cover:
- A registered handler is invoked for its event_type.
- A handler that raises increments retries and keeps the row PENDING.
- After MAX_RETRIES failures the row is marked DEAD.
- An event with no registered handler is marked DISPATCHED (no-op).
"""

from __future__ import annotations

import pytest

from apps.events.events import EventType
from apps.events.models import OutboxEvent
from apps.events.outbox import subscribe

pytestmark = pytest.mark.django_db


def _seed_event(organization, *, event_type=EventType.SALE_FINALISED, source_doc_id="900"):
    return OutboxEvent.objects.create(
        event_type=event_type,
        payload={"sale_id": source_doc_id},
        source_doc_type="retail.Sale",
        source_doc_id=source_doc_id,
        organization=organization,
    )


def test_dispatcher_calls_registered_handler(organization):
    seen = []

    def handler(ev):
        seen.append((ev.event_type, ev.source_doc_id))

    subscribe(EventType.SALE_FINALISED, handler)

    ev = _seed_event(organization)

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    ev.refresh_from_db()
    assert ev.status == OutboxEvent.Status.DISPATCHED
    assert seen == [(EventType.SALE_FINALISED, "900")]


def test_dispatcher_event_with_no_handler_is_marked_dispatched(organization):
    """An event nobody subscribes to must still move off PENDING."""
    ev = _seed_event(organization, event_type="NoOneCaresAboutThis")

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    ev.refresh_from_db()
    assert ev.status == OutboxEvent.Status.DISPATCHED


def test_dispatcher_retries_on_handler_failure(organization, monkeypatch):
    """A handler that raises keeps the event PENDING with retries+1."""
    calls = []

    def handler(ev):
        calls.append(ev.pk)
        raise RuntimeError("simulated failure")

    subscribe(EventType.PAYROLL_RUN_APPROVED, handler)

    ev = _seed_event(
        organization,
        event_type=EventType.PAYROLL_RUN_APPROVED,
        source_doc_id="PR-1",
    )

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    ev.refresh_from_db()
    assert ev.status == OutboxEvent.Status.PENDING
    assert ev.retries == 1
    assert "simulated failure" in ev.last_error
    assert calls == [ev.pk]


def test_dispatcher_dead_letters_after_max_retries(organization, monkeypatch):
    """After OutboxEvent.MAX_RETRIES failures the event moves to DEAD."""

    def handler(ev):
        raise RuntimeError("always fails")

    subscribe(EventType.STATUTORY_FILING_GENERATED, handler)

    ev = _seed_event(
        organization,
        event_type=EventType.STATUTORY_FILING_GENERATED,
        source_doc_id="SF-1",
    )
    # Simulate the row having already failed MAX_RETRIES times.
    OutboxEvent.objects.filter(pk=ev.pk).update(retries=OutboxEvent.MAX_RETRIES)

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    ev.refresh_from_db()
    assert ev.status == OutboxEvent.Status.DEAD
    assert ev.retries == OutboxEvent.MAX_RETRIES + 1


def test_dispatcher_only_processes_pending_rows(organization):
    """DISPATCHED / DEAD rows are skipped."""
    seen = []
    subscribe(EventType.SALE_FINALISED, lambda ev: seen.append(ev.pk))

    OutboxEvent.objects.create(
        event_type=EventType.SALE_FINALISED,
        payload={},
        source_doc_type="retail.Sale",
        source_doc_id="A",
        organization=organization,
        status=OutboxEvent.Status.DISPATCHED,
    )
    pending = _seed_event(organization, source_doc_id="B")

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    assert seen == [pending.pk]


def test_dispatcher_clears_lock_after_dispatch(organization):
    """After successful dispatch the soft lock is cleared (admin view shows it free)."""

    def handler(ev):
        pass

    subscribe(EventType.SALE_FINALISED, handler)

    ev = _seed_event(organization)

    from django.core.management import call_command

    call_command("run_outbox_dispatcher", "--once")

    ev.refresh_from_db()
    assert ev.locked_at is None
    assert ev.locked_by == ""
