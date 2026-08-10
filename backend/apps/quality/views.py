"""Quality API.

Every transition is an action, not a PATCH. A case does not move from
"investigating" to "closed" because somebody set a field — it moves because a
rule was satisfied, and the rule lives in `services`.
"""

from __future__ import annotations

from typing import Any, cast

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.quality import services
from apps.quality.models import CapaAction, QualityCase
from apps.quality.serializers import CapaActionSerializer, QualityCaseSerializer


class QualityAccess(BasePermission):
    """Anyone may raise a case. Deciding one needs quality authority.

    Raising is deliberately open: the person who notices a problem is usually
    a cashier or a driver, and a system that makes reporting hard gets fewer
    reports rather than fewer problems.
    """

    message = "You do not have authority over quality cases."
    WRITE_CODES = ("inventory.adjust", "organization.manage", "catalog.manage")

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS", "POST"):
            return True
        return any(user.has_permission(code) for code in self.WRITE_CODES)


def _decider(user: User) -> bool:
    return any(
        user.has_permission(code)
        for code in ("inventory.adjust", "organization.manage", "catalog.manage")
    )


class QualityCaseViewSet(viewsets.ModelViewSet):
    """Complaints, deviations and adverse events — one list, filtered by kind."""

    permission_classes = [IsAuthenticated, QualityAccess]
    serializer_class = QualityCaseSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = cast(User, self.request.user)
        qs = QualityCase.objects.select_related("product", "batch", "owner").prefetch_related(
            "actions"
        )
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        params = self.request.query_params
        for field in ("kind", "status", "severity", "source"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("open") == "true":
            qs = qs.exclude(status__in=["CLOSED", "REJECTED"])
        if params.get("batch"):
            qs = qs.filter(batch_id=params["batch"])
        return qs

    def perform_create(self, serializer: Any) -> None:
        data = dict(serializer.validated_data)
        try:
            case = services.open_case(
                user=cast(User, self.request.user),
                adverse_event=self.request.data.get("adverse_event"),
                **data,
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        serializer.instance = case

    @action(detail=True, methods=["post"])
    def investigate(self, request: Request, pk: str | None = None) -> Response:
        case = self.get_object()
        try:
            services.record_investigation(
                case=case,
                investigation=str(request.data.get("investigation", "")),
                root_cause=str(request.data.get("root_cause", "")),
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=["post"], url_path="add-action")
    def add_action(self, request: Request, pk: str | None = None) -> Response:
        case = self.get_object()
        owner_id = request.data.get("owner")
        try:
            services.add_action(
                case=case,
                description=str(request.data.get("description", "")),
                kind=str(request.data.get("kind", CapaAction.Kind.CORRECTIVE)),
                owner=User.objects.filter(pk=owner_id).first() if owner_id else None,
                due_date=request.data.get("due_date") or None,
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        case.refresh_from_db()
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        case = self.get_object()
        if not _decider(cast(User, request.user)):
            raise ValidationError("Closing a quality case needs quality authority.")
        try:
            services.close_case(
                case=case, note=str(request.data.get("note", "")), user=cast(User, request.user)
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=["post"], url_path="report-to-regulator")
    def report_to_regulator(self, request: Request, pk: str | None = None) -> Response:
        """Record that this went to the authority, and under what reference.

        Kept as an explicit act with a reference rather than a flag, because
        "we reported it" is a claim somebody will have to evidence.
        """
        case = self.get_object()
        reference = str(request.data.get("reference", "")).strip()
        if not reference:
            raise ValidationError({"reference": "Record the reference the regulator gave you."})
        case.reported_to_regulator_at = timezone.now()
        case.regulator_reference = reference
        case.save(update_fields=["reported_to_regulator_at", "regulator_reference", "updated_at"])
        return Response(self.get_serializer(case).data)

    @action(detail=False, methods=["get"])
    def workload(self, request: Request) -> Response:
        user = cast(User, request.user)
        org = request.query_params.get("organization") or user.organization_id
        return Response(services.open_workload(organization=org))


class CapaActionViewSet(viewsets.ReadOnlyModelViewSet):
    """Actions across every case — the "what is on my plate" list."""

    permission_classes = [IsAuthenticated, QualityAccess]
    serializer_class = CapaActionSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = cast(User, self.request.user)
        qs = CapaAction.objects.select_related("case", "owner", "verified_by")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(case__organization__in=organizations_visible_to(user))
        params = self.request.query_params
        if params.get("mine") == "true":
            qs = qs.filter(owner=user)
        if params.get("open") == "true":
            qs = qs.exclude(status=CapaAction.Status.VERIFIED)
        if params.get("overdue") == "true":
            qs = qs.filter(due_date__lt=timezone.localdate()).exclude(
                status=CapaAction.Status.VERIFIED
            )
        return qs

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        item = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            services.complete_action(
                action=item,
                note=str(request.data.get("note", "")),
                user=cast(User, request.user),
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk: str | None = None) -> Response:
        item = get_object_or_404(self.get_queryset(), pk=pk)
        user = cast(User, request.user)
        if not _decider(user):
            raise ValidationError("Verifying effectiveness needs quality authority.")
        effective = request.data.get("effective", True)
        try:
            services.verify_action(
                action=item,
                effective=effective not in (False, "false", "0", 0),
                note=str(request.data.get("note", "")),
                user=user,
            )
        except services.QualityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(item).data)
