"""What a quality case looks like over the wire."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.quality.models import AdverseEventDetail, CapaAction, QualityCase


class CapaActionSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default="")
    verified_by_name = serializers.CharField(
        source="verified_by.get_full_name", read_only=True, default=""
    )
    is_overdue = serializers.BooleanField(read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CapaAction
        fields = [
            "id",
            "case",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "description",
            "owner",
            "owner_name",
            "due_date",
            "is_overdue",
            "completed_at",
            "completion_note",
            "verified_at",
            "verified_by",
            "verified_by_name",
            "effectiveness_note",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "completed_at",
            "verified_at",
            "verified_by",
            "created_at",
        ]


class AdverseEventDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdverseEventDetail
        exclude = ["id", "case"]


class QualityCaseSerializer(serializers.ModelSerializer):
    actions = CapaActionSerializer(many=True, read_only=True)
    adverse_event = AdverseEventDetailSerializer(read_only=True)
    product_name = serializers.CharField(source="product.generic_name", read_only=True, default="")
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default="")
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    outstanding_actions = serializers.IntegerField(read_only=True)
    #: The lot this case is about, whether or not we ever held it. A patient
    #: complaining about a pack bought elsewhere still names a batch.
    batch_label = serializers.SerializerMethodField()

    def get_batch_label(self, obj: QualityCase) -> str:
        batch = obj.batch
        return batch.batch_number if batch else obj.batch_number

    class Meta:
        model = QualityCase
        fields = [
            "id",
            "case_number",
            "organization",
            "kind",
            "kind_display",
            "source",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "title",
            "description",
            "product",
            "product_name",
            "batch",
            "batch_number",
            "batch_label",
            "reported_by",
            "reporter_name",
            "reporter_contact",
            "owner",
            "owner_name",
            "due_date",
            "investigation",
            "root_cause",
            "is_reportable",
            "reported_to_regulator_at",
            "regulator_reference",
            "outstanding_actions",
            "actions",
            "adverse_event",
            "closed_at",
            "closure_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "case_number",
            "status",
            "reported_by",
            "investigation",
            "root_cause",
            "closed_at",
            "closure_note",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # A case about a batch we hold should point at the row, not repeat the
        # number as text — otherwise a recall search misses it.
        if attrs.get("batch") and attrs.get("batch_number"):
            attrs["batch_number"] = ""
        return attrs
