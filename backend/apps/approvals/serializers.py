from __future__ import annotations

from rest_framework import serializers

from apps.approvals.models import ApprovalRequest


class ApprovalRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    claimed_by_name = serializers.CharField(
        source="claimed_by.username", read_only=True, default=None
    )
    decided_by_name = serializers.CharField(
        source="decided_by.username", read_only=True, default=None
    )
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    sla_deadline = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "resource_type",
            "resource_id",
            "organization",
            "organization_name",
            "requested_by",
            "requested_by_name",
            "payload",
            "reason",
            "status",
            "claimed_by",
            "claimed_by_name",
            "claimed_at",
            "sla_hours",
            "sla_deadline",
            "sla_breached",
            "is_overdue",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "decision_note",
            "created_at",
        ]
        read_only_fields = fields
