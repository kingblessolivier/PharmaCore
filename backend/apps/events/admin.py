"""Admin registration for the OutboxEvent model (F1 ships a thin listing).

The full event-detail UI lands in F1.4 alongside the dispatcher command.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin

from .models import OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "status",
        "organization",
        "retries",
        "occurred_at",
        "last_attempt_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("event_type", "source_doc_type", "source_doc_id", "last_error")
    readonly_fields = (
        "event_type",
        "payload",
        "source_doc_type",
        "source_doc_id",
        "source_line_id",
        "occurred_at",
        "retries",
        "last_error",
        "last_attempt_at",
        "locked_at",
        "locked_by",
        "created_by",
    )

    def has_add_permission(self, request: Any) -> bool:  # events come from publish()
        return False
