"""``OutboxEvent`` — the durable log of domain events awaiting dispatch.

Written inside a business transaction via :func:`apps.events.outbox.publish`
which schedules the actual DB write for ``transaction.on_commit`` — so a
rolled-back transaction leaves **no event** (transactional outbox pattern,
Frederic Brooks / Microsoft patterns).

Consumed by the ``run_outbox_dispatcher`` management command (or a Celery
task). Consumers must be **idempotent on ``(event_type, source_doc_id,
source_line_id)``** — replays are normal after a transient failure.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class OutboxEvent(models.Model):
    """One event waiting to be dispatched to its handlers.

    The dispatcher claims rows with ``SELECT … FOR UPDATE SKIP LOCKED``,
    hands them to the registered handler for their ``event_type``, and on
    success marks them ``DISPATCHED``. On failure it increments ``retries``
    and stores ``last_error``; after ``MAX_RETRIES`` it moves to ``DEAD``.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending dispatch"
        DISPATCHED = "DISPATCHED", "Dispatched successfully"
        DEAD = "DEAD", "Exhausted retries (dead-letter)"

    #: Maximum dispatcher attempts before the event is dead-lettered.
    MAX_RETRIES = 8

    event_type = models.CharField(max_length=64)
    # JSONB-ish payload — the source of truth for the handler. Keep it small
    # and reference other rows by id (e.g. ``"sale_id": 123``); don't embed
    # full denormalised copies of large records.
    payload = models.JSONField(default=dict, blank=True)

    # Where the event came from. Used for idempotency: consumers dedupe on
    # ``(event_type, source_doc_id, source_line_id)``.
    source_doc_type = models.CharField(max_length=50, blank=True, default="")
    source_doc_id = models.CharField(max_length=64, blank=True, default="")
    source_line_id = models.CharField(max_length=64, blank=True, default="")

    # Tenant scoping — events always belong to one org.
    organization = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="outbox_events",
        help_text="Tenant scope. Null for cross-tenant events (e.g. platform announcements).",
    )

    occurred_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    retries = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    # Lightweight worker lock — the dispatcher sets ``locked_at`` on claim and
    # clears it on release so other workers don't pick the same row. Soft lock
    # only — there's also ``SELECT … FOR UPDATE SKIP LOCKED`` at the SQL level
    # which is the real concurrency guarantee.
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=80, blank=True, default="")

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            # Hot path: dispatcher fetches the oldest PENDING events per org.
            models.Index(fields=["status", "id"]),
            # Replay / dedupe / debugging.
            models.Index(
                fields=["event_type", "source_doc_type", "source_doc_id", "source_line_id"],
                name="idx_outbox_idempotency",
            ),
        ]
        constraints = [
            # The dispatcher MUST NOT have two rows for the same logical event
            # even after retries — replays come from the same row, not a new one.
            models.UniqueConstraint(
                fields=[
                    "event_type",
                    "source_doc_type",
                    "source_doc_id",
                    "source_line_id",
                ],
                name="uniq_outbox_idempotency",
            )
        ]

    def __str__(self) -> str:
        subject = self.source_doc_id or "—"
        return f"{self.event_type}#{self.pk} ({self.status}) {subject}"

    @property
    def is_due(self) -> bool:
        """Used by the dispatcher's claim query — dead rows are excluded."""
        return self.status == self.Status.PENDING
