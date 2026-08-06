"""Domain event bus — cross-cutting primitive for HR ↔ Finance ↔ Distribution ↔
Inventory ↔ Retail integration.

ROADMAP §9/§10 + ADR-010. Subsystems publish events via :func:`apps.events.outbox.publish`
inside a ``transaction.on_commit`` callback so a rolled-back transaction leaves no
event. A separate dispatcher (``run_outbox_dispatcher``) consumes them; consumers
**must be idempotent on ``(event_type, source_doc_id, source_line_id)``**.
"""

from __future__ import annotations

from .events import EventType  # noqa: F401  (re-export for convenience)
from .outbox import OutboxError, publish, subscribe  # noqa: F401

__all__ = ["EventType", "OutboxError", "publish", "subscribe"]