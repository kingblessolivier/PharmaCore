"""Internal audit API.

Kept beside the quality API rather than in its own app, because a finding that
matters becomes a quality case and the two are read together.
"""

from __future__ import annotations

from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.quality import services
from apps.quality.models import AuditEngagement, AuditFinding


class AuditFindingSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    #: The CAPA a serious finding raised. Its number is what somebody follows
    #: to see whether the finding was actually dealt with.
    case_number = serializers.CharField(source="case.case_number", read_only=True, default="")
    case_status = serializers.CharField(source="case.status", read_only=True, default="")

    class Meta:
        model = AuditFinding
        fields = [
            "id",
            "engagement",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "observation",
            "requirement",
            "management_response",
            "responded_at",
            "case",
            "case_number",
            "case_status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "responded_at", "case", "created_at"]


class AuditEngagementSerializer(serializers.ModelSerializer):
    findings = AuditFindingSerializer(many=True, read_only=True)
    lead_auditor_name = serializers.CharField(
        source="lead_auditor.get_full_name", read_only=True, default=""
    )
    subject_name = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    open_findings = serializers.IntegerField(read_only=True)

    def get_subject_name(self, obj: AuditEngagement) -> str:
        if obj.subject_organization:
            return obj.subject_organization.name
        if obj.subject_supplier:
            return obj.subject_supplier.name
        return "—"

    class Meta:
        model = AuditEngagement
        fields = [
            "id",
            "reference",
            "organization",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "title",
            "scope",
            "subject_organization",
            "subject_supplier",
            "subject_name",
            "lead_auditor",
            "lead_auditor_name",
            "planned_for",
            "started_at",
            "completed_at",
            "summary",
            "open_findings",
            "findings",
            "created_at",
        ]
        read_only_fields = ["id", "reference", "status", "completed_at", "summary", "created_at"]


class AuditEngagementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AuditEngagementSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = cast(User, self.request.user)
        qs = AuditEngagement.objects.select_related(
            "lead_auditor", "subject_organization", "subject_supplier"
        ).prefetch_related("findings", "findings__case")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("open") == "true":
            qs = qs.exclude(status=AuditEngagement.Status.CLOSED)
        return qs

    def perform_create(self, serializer: Any) -> None:
        try:
            serializer.instance = services.plan_audit(
                user=cast(User, self.request.user), **serializer.validated_data
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc

    @action(detail=True, methods=["post"], url_path="add-finding")
    def add_finding(self, request: Request, pk: str | None = None) -> Response:
        engagement = self.get_object()
        try:
            services.raise_finding(
                engagement=engagement,
                observation=str(request.data.get("observation", "")),
                severity=str(request.data.get("severity", "MINOR")),
                requirement=str(request.data.get("requirement", "")),
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        engagement.refresh_from_db()
        return Response(self.get_serializer(engagement).data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        engagement = self.get_object()
        try:
            services.close_audit(
                engagement=engagement,
                summary=str(request.data.get("summary", "")),
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(engagement).data)


class AuditFindingViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AuditFindingSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = cast(User, self.request.user)
        qs = AuditFinding.objects.select_related("engagement", "case")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(engagement__organization__in=organizations_visible_to(user))
        if self.request.query_params.get("open") == "true":
            qs = qs.exclude(status=AuditFinding.Status.CLOSED)
        return qs

    @action(detail=True, methods=["post"])
    def respond(self, request: Request, pk: str | None = None) -> Response:
        finding = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            services.respond_to_finding(
                finding=finding,
                response=str(request.data.get("response", "")),
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(finding).data)
