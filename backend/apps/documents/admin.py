from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.documents.models import Document, DocumentSequence


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "doc_type", "year", "next_number")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("doc_number", "doc_type", "organization", "generated_at")
    list_filter = ("doc_type",)
    search_fields = ("doc_number", "reference_id")

    # Write-once: read-only in the admin.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False
