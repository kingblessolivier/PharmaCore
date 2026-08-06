"""The OutboxEvent dispatcher.

Consumes pending rows from :class:`apps.events.models.OutboxEvent` and runs
each handler registered for its event type. The contract is **idempotent
handler** — replays are normal.

Run with ``python manage.py run_outbox_dispatcher`` either as a one-shot
loop (sleep ``--interval`` seconds between passes) or as a long-running
worker. A production deployment should run this as a Celery task or a
Kubernetes CronJob; the management command keeps it operable in dev.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.events.models import OutboxEvent
from apps.events.outbox import get_handlers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dispatch pending OutboxEvent rows to their registered handlers."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Maximum events to claim per pass (default: 100).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Seconds to sleep between passes when --loop is set (default: 2.0).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single pass and exit (default).",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Loop forever, sleeping --interval seconds between passes.",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        batch_size: int = opts["batch_size"]
        interval: float = opts["interval"]
        once: bool = opts["once"]
        loop: bool = opts["loop"]

        if once and loop:
            self.stderr.write("Choose either --once or --loop, not both.")
            return

        while True:
            processed = self._dispatch_pass(batch_size=batch_size)
            if once:
                self.stdout.write(f"Dispatched {processed} event(s); exiting (--once).")
                return
            if processed == 0:
                # Quiet loop when there's nothing to do.
                self.stdout.write("No pending events; idle.")
            time.sleep(interval)

    # ------------------------------------------------------------------

    def _dispatch_pass(self, *, batch_size: int) -> int:
        """Claim and dispatch up to ``batch_size`` pending events.

        Returns the number of rows we tried to dispatch (regardless of
        success / failure — the dispatcher records the failure on the row
        and moves on).
        """
        # SELECT … FOR UPDATE SKIP LOCKED — multiple workers can run in
        # parallel without claiming the same row. SQLite ignores SKIP LOCKED
        # semantics, but the in-process transaction lock is sufficient for
        # dev; production runs on Postgres.
        claimed = self._claim_pending(batch_size=batch_size)
        if not claimed:
            return 0
        for event in claimed:
            self._handle_event(event)
        return len(claimed)

    def _claim_pending(self, *, batch_size: int) -> list[OutboxEvent]:
        """Atomically claim a batch of pending events for this worker."""
        with transaction.atomic():
            qs = (
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING)
                .order_by("id")[:batch_size]
            )
            rows = list(qs)
            # Soft-lock: mark who took them so the admin view shows worker state.
            if rows:
                now = timezone.now()
                worker = self._worker_id()
                OutboxEvent.objects.filter(pk__in=[r.pk for r in rows]).update(
                    locked_at=now, locked_by=worker
                )
            return rows

    def _handle_event(self, event: OutboxEvent) -> None:
        handlers = get_handlers(event.event_type)
        if not handlers:
            logger.info(
                "OutboxEvent %s has no registered handler; marking DISPATCHED.",
                event.pk,
            )
            self._mark_dispatched(event)
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 — we record & retry
                self._mark_failed(event, exc)
                return
        self._mark_dispatched(event)

    # ------------------------------------------------------------------

    def _mark_dispatched(self, event: OutboxEvent) -> None:
        event.status = OutboxEvent.Status.DISPATCHED
        event.last_attempt_at = timezone.now()
        event.locked_at = None
        event.locked_by = ""
        event.save(
            update_fields=["status", "last_attempt_at", "locked_at", "locked_by"]
        )

    def _mark_failed(self, event: OutboxEvent, exc: Exception) -> None:
        event.retries = (event.retries or 0) + 1
        event.last_error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        event.last_attempt_at = timezone.now()
        event.locked_at = None
        event.locked_by = ""
        if event.retries >= OutboxEvent.MAX_RETRIES:
            event.status = OutboxEvent.Status.DEAD
            logger.error(
                "OutboxEvent %s exhausted retries (%d); moving to DEAD. "
                "Last error: %s",
                event.pk,
                event.retries,
                event.last_error,
            )
        event.save(
            update_fields=[
                "retries",
                "last_error",
                "last_attempt_at",
                "locked_at",
                "locked_by",
                "status",
            ]
        )

    @staticmethod
    def _worker_id() -> str:
        import os
        import socket

        return f"{socket.gethostname()}:{os.getpid()}"