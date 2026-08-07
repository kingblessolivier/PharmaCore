"""The transactional outbox API.

Producers call :func:`publish` inside their service method. The event row is
actually written in ``transaction.on_commit`` so a rolled-back transaction
**leaves no event**. The dispatcher (``run_outbox_dispatcher``) consumes the
rows; consumers register with :func:`subscribe` and must be idempotent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.db import transaction

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.events.models import OutboxEvent

logger = logging.getLogger(__name__)

# A handler signature: ``(OutboxEvent) -> None``. Raises on transient failure
# (the dispatcher will retry); returns ``None`` on success.
Handler = Callable[["OutboxEvent"], None]


class OutboxError(Exception):
    """Raised when a handler fails. The dispatcher catches and retries."""


# Module-level registry of event_type -> list[handler]. The dispatcher walks
# this for every pending event. Kept in-process (not in the DB) because it's
# fast and only ever populated at import time.
_REGISTRY: dict[str, list[Handler]] = {}


def subscribe(event_type: str, handler: Handler) -> None:
    """Register ``handler`` for events of type ``event_type``.

    Multiple handlers per event type are allowed. Handlers must be idempotent
    on ``(event_type, source_doc_id, source_line_id)``.
    """
    _REGISTRY.setdefault(event_type, []).append(handler)
    logger.debug("Subscribed %s to %s", handler, event_type)


def get_handlers(event_type: str) -> list[Handler]:
    return list(_REGISTRY.get(event_type, []))


def publish(
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
    source_doc_type: str = "",
    source_doc_id: str | int = "",
    source_line_id: str | int = "",
    organization_id: int | None = None,
    user: Any | None = None,
) -> OutboxEvent:
    """Schedule an outbox row to be written at transaction commit.

    If we're not inside an ``atomic`` block the row is written immediately —
    the dispatcher can still pick it up.
    """
    # Import here to avoid the apps.events -> apps.events.models cycle on import.
    from .models import OutboxEvent

    payload = payload or {}
    # Stringify ids — the unique constraint spans str columns, and source ids
    # in this codebase may be ints (Django BigAutoField) or UUIDs (per ADR-001).
    sid = str(source_doc_id) if source_doc_id not in (None, "") else ""
    lid = str(source_line_id) if source_line_id not in (None, "") else ""

    def _write() -> OutboxEvent:
        return OutboxEvent.objects.create(
            event_type=event_type,
            payload=payload,
            source_doc_type=source_doc_type,
            source_doc_id=sid,
            source_line_id=lid,
            organization_id=organization_id,
            created_by=user if getattr(user, "pk", None) else None,
        )

    # If we are in an atomic block, defer the write. Otherwise write now.
    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_write)
    else:
        return _write()
    # When on_commit fires we have no handle to return; callers don't need one.
    return None  # type: ignore[return-value]
