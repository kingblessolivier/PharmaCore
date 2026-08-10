"""Tickets over the wire."""

from __future__ import annotations

from rest_framework import serializers

from apps.servicedesk.models import Ticket, TicketNote


class TicketNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True, default="")

    class Meta:
        model = TicketNote
        fields = ["id", "ticket", "author", "author_name", "body", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    notes = TicketNoteSerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True, default=""
    )
    customer_name = serializers.CharField(
        source="customer_organization.name", read_only=True, default=""
    )
    product_name = serializers.CharField(source="product.generic_name", read_only=True, default="")
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    #: The clock. `is_breached` is what the queue is sorted and judged by.
    is_breached = serializers.BooleanField(read_only=True)
    hours_remaining = serializers.FloatField(read_only=True)
    quality_case_number = serializers.CharField(
        source="quality_case.case_number", read_only=True, default=""
    )

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_number",
            "organization",
            "category",
            "category_display",
            "priority",
            "priority_display",
            "status",
            "status_display",
            "subject",
            "body",
            "customer_organization",
            "customer_name",
            "contact_name",
            "contact_phone",
            "order_reference",
            "product",
            "product_name",
            "assigned_to",
            "assigned_to_name",
            "due_at",
            "is_breached",
            "hours_remaining",
            "first_response_at",
            "resolved_at",
            "resolution",
            "quality_case",
            "quality_case_number",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "status",
            "due_at",
            "first_response_at",
            "resolved_at",
            "resolution",
            "quality_case",
            "created_at",
            "updated_at",
        ]
